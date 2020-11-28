#!/usr/bin/python
from .. import zoned
from transcode.util import cached, numpify
import numpy
from fractions import Fraction as QQ
import itertools
from av.video import VideoFrame
import sys
from collections import OrderedDict


class Zone(zoned.Zone):
    getinitkwargs = ["src_start", "src_fps", "pulldown",
                     "pulldownoffset", "yblend", "uvblend"]

    def __init__(self, src_start, src_fps=QQ(24000, 1001), pulldown=None, pulldownoffset=0, yblend=False, uvblend=False, prev=None, next=None, framecount=None, parent=None):
        super().__init__(src_start=src_start, prev=prev, next=next, parent=parent)
        self.src_fps = src_fps
        self.yblend = bool(yblend)
        self.uvblend = bool(uvblend)
        self.pulldown = str(pulldown).upper() if pulldown is not None else None

        if self.pulldown is not None:
            self.pulldownoffset = int(pulldownoffset) % self.old_blksize

        else:
            self.pulldownoffset = 0

        self._reverse_mapping = None
        self._reverse_mapping_head = None
        self._reverse_mapping_tail = None

        self._forward_matrix_blended = None
        self._reverse_matrix_blended = None
        self._reverse_matrix_blended_head = None
        self._reverse_matrix_blended_tail = None
        self._framecount = framecount

    def __getstate__(self):
        state = OrderedDict()
        state["src_fps"] = self.src_fps

        if self.pulldown:
            state["pulldown"] = self.pulldown
            state["pulldownoffset"] = self.pulldownoffset
            state["yblend"] = self.yblend
            state["uvblend"] = self.uvblend

        return state

    def __setstate__(self, state):
        self.src_fps = state["src_fps"]

        if state.get("pulldown"):
            self.pulldown = state["pulldown"]
            self.pulldownoffset = state["pulldownoffset"]
            self.yblend = state["yblend"]
            self.uvblend = state["uvblend"]

    def reset_cache(self):
        super().reset_cache()
        del self.start_pts_time

    def reset_cache_full(self, notify_parent=True):
        super().reset_cache_full(notify_parent=notify_parent)
        del self.reverse_mapping
        del self.reverse_mapping_head
        del self.reverse_mapping_tail
        del self.forward_matrix_blended
        del self.reverse_matrix_blended
        del self.reverse_matrix_blended_head
        del self.reverse_matrix_blended_tail

    @cached
    def framecount(self):
        prev_framecount = self.prev_framecount
        if prev_framecount is None:
            return None
        if self.pulldown is not None:
            q, r = divmod(self.pulldownoffset +
                          prev_framecount - 1, self.old_blksize)
            return int(q*self.new_blksize + self._pattern_int[r].min() + 1 - self.new_offset)
        else:
            return int(prev_framecount)

    def _translate_fields(self, N):
        if self.pulldown is not None:
            q, r = divmod(self.pulldownoffset + N, self.old_blksize)
            M = numpy.moveaxis(q*self.new_blksize + numpy.moveaxis(
                self._pattern_int[r], N.ndim, 0) - self.new_offset, 0, N.ndim)

            if isinstance(N, numpy.ndarray):
                NN = self._backtranslate_fields(M[:, 0])
                M[N != NN[:, 0], 0] = -1

                NN = self._backtranslate_fields(M[:, 1])
                M[N != NN[:, 1], 1] = -1
            else:
                NN = self._backtranslate_fields(M[0])
                if N != NN[0]:
                    M[0] = -1

                NN = self._backtranslate_fields(M[1])
                if N != NN[1]:
                    M[1] = -1
            return M
        else:
            M = numpy.moveaxis((N, N), 0, N.ndim)

        return M

    def _backtranslate_fields(self, M):
        M = numpify(M)

        if M.size == 0:
            return numpy.moveaxis(numpy.array((M, M)), 0, M.ndim)

        if self.pulldown is not None:
            q, s = divmod(M + self.new_offset, self.new_blksize)

            rlookup = (q*self.old_blksize + self._pattern_int_rlookup[:, :, s] - self.pulldownoffset).clip(
                min=0, max=self.prev_framecount)
            same_frame_possible = (
                rlookup[0, 1] >= rlookup[1, 0])*(rlookup[1, 1] >= rlookup[0, 0])
            if isinstance(M, numpy.ndarray):
                N = numpy.zeros(M.shape+(2,), dtype=numpy.int0)
                N[~same_frame_possible, 0] = rlookup[0, 0][~same_frame_possible]
                N[~same_frame_possible, 1] = rlookup[1, 0][~same_frame_possible]
                N[same_frame_possible, 0] = numpy.maximum(
                    rlookup[0, 0][same_frame_possible], rlookup[1, 0][same_frame_possible])
                N[same_frame_possible, 1] = numpy.maximum(
                    rlookup[0, 0][same_frame_possible], rlookup[1, 0][same_frame_possible])
                return N
            else:
                if same_frame_possible:
                    return numpy.array((numpy.maximum(rlookup[0, 0], rlookup[1, 0]),)*2)
                else:
                    return rlookup[:, 0]
        else:
            return numpy.moveaxis(numpy.array((M, M)), 0, M.ndim)

    def translate_fields(self, n):
        n = numpify(n)
        N = n - self.prev_start
        M = self._translate_fields(N)
        nonneg = M >= 0
        m = -numpy.ones(M.shape, dtype=numpy.int0)
        m[nonneg] = M[nonneg] + self.dest_start
        return m

    def backtranslate_fields(self, m):
        m = numpify(m)
        M = m - self.dest_start
        N = self._backtranslate_fields(M)
        return N + self.prev_start

    @zoned.Zone.indexMapLocal.getter
    def indexMapLocal(self):
        if self.pulldown is not None:
            N = numpy.arange(0, self.prev_framecount)
            q, r = divmod(self.pulldownoffset + N, self.old_blksize)
            indexMapLocal = q*self.new_blksize + \
                self._pattern_int[r, 0] - self.new_offset
            NN = -numpy.ones(indexMapLocal.shape, dtype=numpy.int0)
            filt = (indexMapLocal >= 0)*(indexMapLocal < self.framecount)
            NN[filt] = self.reverseIndexMapLocal[indexMapLocal[filt]]
            indexMapLocal[NN != N] = -1

        else:
            indexMapLocal = numpy.arange(0, self.prev_framecount)

        return indexMapLocal

    @zoned.Zone.reverseIndexMapLocal.getter
    def reverseIndexMapLocal(self):
        M = numpy.arange(0, self.framecount)
        if self.pulldown is not None:
            q, s = divmod(M + self.new_offset, self.new_blksize)

            rlookup = (q*self.old_blksize + self._pattern_int_rlookup[:, :, s] - self.pulldownoffset).clip(
                min=0, max=self.prev_framecount)
            same_frame_possible = (
                rlookup[0, 1] >= rlookup[1, 0])*(rlookup[1, 1] >= rlookup[0, 0])

            if isinstance(M, numpy.ndarray):
                N = numpy.zeros(M.shape, dtype=numpy.int0)
                N[~same_frame_possible] = rlookup[0, 0][~same_frame_possible]
                N[same_frame_possible] = numpy.maximum(
                    rlookup[0, 0][same_frame_possible], rlookup[1, 0][same_frame_possible])

            else:
                if same_frame_possible:
                    N = numpy.maximum(rlookup[0, 0], rlookup[1, 0])

                else:
                    N = rlookup[0, 0]

        else:
            N = M

        return N  # + self.prev_start

    def getIterStart(self, start):
        if self.pulldown is not None:
            if start < self.dest_start + self.new_blksize_head:
                return self.prev_start

            q, s = divmod(start - (self.dest_start +
                                   self.new_blksize_head), self.new_blksize)
            A = self.backtranslate_fields(
                self.dest_start + self.new_blksize_head + q*self.new_blksize)
            return A[A >= 0].min()

        else:
            return self.reverseIndexMap[start - self.dest_start]

    def getIterEnd(self, end):
        if self.pulldown is not None:
            if end > self.dest_end - self.new_blksize_tail:
                return self.prev_end

            q, s = divmod(end + self.new_blksize - 1 -
                          (self.dest_start + self.new_blksize_head), self.new_blksize)
            return self.prev_start + self.old_blksize_head + q*self.old_blksize + 1

        else:
            return self.reverseIndexMap[end - self.dest_start]

    @property
    def evens(self):
        return self._evens

    @property
    def odds(self):
        return self._odds

    @property
    def old_blksize(self):
        return self._old_blksize

    @property
    def new_blksize(self):
        return self._new_blksize

    @property
    def new_offset(self):
        return self._pattern_int[self.pulldownoffset].max()

    @property
    def old_blksize_head(self):
        return self.old_blksize - self.pulldownoffset

    @property
    def new_blksize_head(self):
        return self.new_blksize - self.new_offset % self.new_blksize

    @property
    def old_end_offset(self):
        return (self.pulldownoffset + self.prev_framecount) % self.old_blksize

    @property
    def new_end_offset(self):
        if self.old_end_offset == 0:
            return 0
        return self._pattern_int[self.old_end_offset - 1].min() + 1

    @property
    def old_blksize_tail(self):
        return (self.old_end_offset - 1) % self.old_blksize + 1

    @property
    def new_blksize_tail(self):
        return (self.new_end_offset - 1) % self.new_blksize + 1

    @property
    def pulldown(self):
        return self._pattern

    @pulldown.setter
    def pulldown(self, value):
        if value is not None:
            value = value.upper()

            if len(value) % 2:
                raise ValueError("Telecine pattern must be even-length.")

            if "A" not in value[:2]:
                raise ValueError(
                    "Telecine pattern contain 'A' in position 0 or position 1.")

            if (self.yblend or self.uvblend) and not value.startswith("AA"):
                raise ValueError(
                    "Telecine pattern must begin with AA if either yblend or uvblend is set.")

            if hasattr(self, "_pattern") and value != self._pattern:
                self.reset_cache_full()

            self._evens = value[::2]
            evens_start = min(self.evens.replace("*", ""))
            evens_end = max(self.evens.replace("*", ""))

            self._odds = value[1::2]
            odds_start = min(self.odds.replace("*", ""))
            odds_end = max(self.odds.replace("*", ""))

            self._old_blksize = len(value)//2
            self._new_blksize = min(
                ord(evens_end) - ord(evens_start) + 1, ord(odds_end) - ord(odds_start) + 1)

            for char in range(ord(evens_start), ord(evens_start) + self.new_blksize):
                if chr(char) not in self.evens:
                    raise ValueError(
                        "Invalid telecine pattern. Hint: Missing '%s' from evens." % chr(char))

            for char in range(ord(odds_start), ord(odds_start) + self.new_blksize):
                if chr(char) not in self.odds:
                    raise ValueError(
                        "Invalid telecine pattern. Hint: Missing '%s' from odds." % chr(char))

            self._pattern = value
            self._pattern_int = numpy.array(
                list(map(ord, value))).reshape(len(value)//2, 2) - ord("A")
            alphabet = list(
                map(chr, range(ord(min(value)), ord(max(value))+1)))

            self._pattern_int_rlookup = numpy.array(
                [
                    (
                        [self._evens.find(chr((ord(alpha) - ord(self._evens[0])) % self.new_blksize + ord(self._evens[0]))) +
                            (ord(alpha) - ord(self._evens[0]))//self.new_blksize*self.old_blksize for alpha in alphabet],
                        [self._evens.rfind(chr((ord(alpha) - ord(self._evens[0])) % self.new_blksize + ord(self._evens[0]))) +
                            (ord(alpha) - ord(self._evens[0]))//self.new_blksize*self.old_blksize for alpha in alphabet],
                    ),
                    (
                        [self._odds.find(chr((ord(alpha) - ord(self._odds[0])) % self.new_blksize + ord(self._odds[0]))) +
                            (ord(alpha) - ord(self._odds[0]))//self.new_blksize*self.old_blksize for alpha in alphabet],
                        [self._odds.rfind(chr((ord(alpha) - ord(self._odds[0])) % self.new_blksize + ord(self._odds[0]))) +
                            (ord(alpha) - ord(self._odds[0]))//self.new_blksize*self.old_blksize for alpha in alphabet],
                    )
                ])
        else:
            if hasattr(self, "_pattern") and value != self._pattern:
                self.reset_cache_full()

            self._evens = None
            self._odds = None
            self._old_blksize = 1
            self._new_blksize = 1
            self._pattern = None

    @property
    def pulldownoffset(self):
        return self._pulldownoffset

    @pulldownoffset.setter
    def pulldownoffset(self, value):
        if hasattr(self, "_pulldownoffset") and value != self._pulldownoffset:
            self.reset_cache_full()

        self._pulldownoffset = value

    @property
    def src_fps(self):
        return self._src_fps

    @src_fps.setter
    def src_fps(self, value):
        if hasattr(self, "_src_fps") and value != self._src_fps:
            self.reset_cache_full()

        self._src_fps = value
        self.src_fps_float = float(value)

    @property
    def dest_fps(self):
        if self.pulldown is not None:
            return self.src_fps*self.new_blksize/self.old_blksize

        else:
            return self.src_fps

    @property
    def dest_fps_float(self):
        if self.pulldown is not None:
            return self.src_fps_float*self.new_blksize/self.old_blksize

        else:
            return self.src_fps_float

    @cached
    def duration(self):
        return self.framecount/self.dest_fps_float

    @cached
    def start_pts_time(self):
        start_pts = self.parent.start_pts_time
        zone = self.prev

        while zone is not None:
            start_pts += zone.duration
            zone = zone.prev

        return start_pts

    @property
    def end_pts_time(self):
        return self.start_pts_time + self.duration

    @cached
    def pts_time_local(self):
        if self.dest_end is None:
            return

        m = numpy.arange(self.dest_start, self.dest_end)
        return (m - self.dest_start)/self.dest_fps_float

    @pts_time_local.deleter
    def pts_time_local(self):
        del self.pts_time
        del self.pts

        if self.parent is not None:
            del self.parent.pts_time

    @cached
    def reverse_mapping(self):
        return self._calc_reverse_mapping()

    @cached
    def reverse_mapping_head(self):
        return self._calc_reverse_mapping(self.pulldownoffset)

    @cached
    def reverse_mapping_tail(self):
        return self._calc_reverse_mapping()[:self.new_blksize_tail]

    def _calc_reverse_mapping(self, offset=0):
        if self.pulldown is not None:
            pattern = self._pattern_int
            fcf = pattern[0].max()
            fe, fo = pattern[0]
            pw = pattern.max() + 1
            K = numpy.arange(pw)
            found = numpy.zeros((pw, 2), dtype=bool)
            find = -numpy.ones((pw, 2), dtype=numpy.int0)
            rfind = -numpy.ones((pw, 2), dtype=numpy.int0)

            for k, (e, o) in enumerate(pattern):
                qe, re = divmod(e - fcf, self.new_blksize)

                if not found[re, 0] and k - qe*self.old_blksize >= offset:
                    find[re, 0] = k - qe*self.old_blksize
                    rfind[re, 0] = k - qe*self.old_blksize
                    found[re, 0] = True

                elif k - qe*self.old_blksize >= offset:
                    if find[re, 0] == 1 + k - qe*self.old_blksize:
                        find[re, 0] = k - qe*self.old_blksize

                    if rfind[re, 0] == k - qe*self.old_blksize - 1:
                        rfind[re, 0] = k - qe*self.old_blksize

                qo, ro = divmod(o - fcf, self.new_blksize)

                if not found[ro, 1] and k - qo*self.old_blksize >= offset:
                    find[ro, 1] = k - qo*self.old_blksize
                    rfind[ro, 1] = k - qo*self.old_blksize
                    found[ro, 1] = True

                elif k - qo*self.old_blksize >= offset:
                    if find[ro, 1] == 1 + k - qo*self.old_blksize:
                        find[ro, 1] = k - qo*self.old_blksize

                    if rfind[ro, 1] == k - qo*self.old_blksize - 1:
                        rfind[ro, 1] = k - qo*self.old_blksize

            bothfound = found.all(axis=1)

            if not bothfound.all():
                k = bothfound.argmax()

            else:
                k = 0

            if not bothfound[k:].all():
                K = bothfound[k:].argmin() + k

            else:
                K = len(bothfound)

            common = (rfind[:, 0] >= find[:, 1])*(rfind[:, 1] >= find[:, 0])
            results = numpy.zeros(find.shape, dtype=numpy.int0)
            results[common, 0] = find[common].max(axis=1)
            results[common, 1] = find[common].max(axis=1)
            results[~common] = find[~common]
            return results[k:K] - offset

        else:
            return [0]

    @cached
    def forward_matrix_blended(self):
        if self.pulldown:
            M = numpy.zeros((self.old_blksize + 1, self.new_blksize + 1))
            M[numpy.arange(self.old_blksize), self._pattern_int[:, 0]] += 0.5
            M[numpy.arange(self.old_blksize), self._pattern_int[:, 1]] += 0.5
            M[-1, -1] = 1
            return numpy.matrix(M)

        else:
            return numpy.matrix(numpy.identity(1))

    @cached
    def reverse_matrix_blended(self):
        if self.pulldown is None:
            return

        M = self.forward_matrix_blended
        A = numpy.array(((M.transpose()*M)**-1*M.transpose())
                        [:self.new_blksize])
        return A[:self.new_blksize]

    @cached
    def reverse_matrix_blended_head(self):
        if self.pulldown is None:
            return

        M = self.forward_matrix_blended

        if self.prev_end <= self.prev_start + self.old_blksize_head:
            cutoff_rows = self.pulldownoffset
            cutoff_columns = self._pattern_int[cutoff_rows].min()
            partials = self._pattern_int[cutoff_rows].max() - cutoff_columns
            M = M[cutoff_rows:cutoff_rows +
                  self.prev_framecount, cutoff_columns:]

            while (M[:, -1] == 0).all():
                M = M[:, :-1]

            inv = ((M.transpose()*M)**-1*M.transpose())[partials:]
            return numpy.array(inv)[:self.framecount]

        else:
            cutoff_rows = self.pulldownoffset
            cutoff_columns = self._pattern_int[cutoff_rows].min()
            partials = self._pattern_int[cutoff_rows].max() - cutoff_columns
            M = M[cutoff_rows:, cutoff_columns:]
            return numpy.array(((M.transpose()*M)**-1*M.transpose())[partials:])

    @cached
    def reverse_matrix_blended_tail(self):
        if self.pulldown is None:
            return

        M = self.forward_matrix_blended[:self.old_blksize_tail,
                                        :self._pattern_int[self.old_blksize_tail-1].max()+1]
        return numpy.array(((M.transpose()*M)**-1*M.transpose())[:self.new_blksize_tail])

    def _copyFrames(self, iterable, prev_start):
        dest_index = itertools.count(
            prev_start + self.dest_start - self.prev_start)

        for k, frame in zip(dest_index, iterable):
            frame.time_base = self.parent.time_base
            frame.pts = self.pts[k - self.dest_start]
            yield frame

    def _pullupBlock(self, frames, frames_yuv, inv_matrix, dest_index, fields):
        framesreturned = False
        for (e, o), row, k in zip(fields, inv_matrix, dest_index):
            """Do we have the data to create this frame?"""
            if e == o:
                try:
                    if frames[e] is None:
                        raise IndexError

                except IndexError:
                    if framesreturned:
                        break

                    continue

                frame = frames[e]
                frame.time_base = self.parent.time_base

                try:
                    frame.pts = self.pts[k - self.dest_start]

                except:
                    raise

                yield frame
                framesreturned = True

            else:
                try:
                    if (self.yblend or self.uvblend):
                        for j, w in enumerate(row):
                            if w != 0 and frames[j] is None:
                                raise IndexError

                    if frames[e] is None or frames[o] is None:
                        raise IndexError

                except IndexError:
                    if framesreturned:
                        break

                    continue

                eframe = frames_yuv[e]
                H, W = eframe.shape
                H = H*2/3
                H = int(H)
                W = int(W)
                oframe = frames_yuv[o]

                if self.yblend:
                    Y = numpy.sum([w*frame[:H] for (w, frame)
                                   in zip(row, frames_yuv) if w != 0], axis=0)
                    Y = numpy.uint8(Y.clip(min=0, max=255) + 0.5)

                else:
                    Ye = eframe[:H:2]
                    Yo = oframe[1:H:2]
                    Y = numpy.moveaxis([Ye, Yo], 0, 1).reshape(H, W)

                if self.uvblend:
                    UV = numpy.sum([w*frame[H:] for (w, frame)
                                    in zip(row, frames_yuv) if w != 0], axis=0)
                    UV = numpy.uint8(UV.clip(min=0, max=255) + 0.5)

                else:
                    Ue = eframe[H:5*H//4, :W//2]
                    Uo = oframe[H:5*H//4, W//2:]
                    U = numpy.concatenate([Ue, Uo], axis=1)
                    Ve = eframe[5*H//4:, :W//2]
                    Vo = oframe[5*H//4:, W//2:]
                    V = numpy.concatenate([Ve, Vo], axis=1)
                    UV = numpy.concatenate([U, V], axis=0)

                YUV = numpy.concatenate((Y, UV), axis=0)
                frame = VideoFrame.from_ndarray(YUV, format="yuv420p")

                frame.time_base = self.parent.time_base
                frame.pts = self.pts[k - self.dest_start]

                yield frame
                framesreturned = True

    def _pullupFrames(self, iterable, prev_start):
        if prev_start < self.prev_start + self.old_blksize_head:
            blk_start = self.prev_start
            next_start = self.prev_start + self.old_blksize_head

        else:
            q, r = divmod(prev_start - (self.prev_start +
                                        self.old_blksize_head), self.old_blksize)
            blk_start = self.prev_start + self.old_blksize_head + q*self.old_blksize
            next_start = min(self.prev_end, blk_start + self.old_blksize)

        for k in range(blk_start, next_start):
            F = self.translate_fields(k)
            dest_start = F.max()

            if dest_start >= 0:
                break

        prev_index = itertools.count(prev_start)
        dest_index = itertools.count(dest_start)
        overlap = max(1, self._pattern_int.max() - self.new_blksize + 1)
        Iterator = zip(prev_index, iterable)

        skip = prev_start - blk_start
        frames = [None]*skip
        frames_yuv = [None]*skip

        while blk_start < self.prev_end:
            fl = next_start - blk_start + overlap
            new_frames = [frame for p_i, frame in itertools.islice(
                Iterator, max(0, fl - len(frames)))]
            frames.extend(new_frames)
            frames_yuv.extend([frame.reformat(format="yuv420p").to_ndarray()
                               if frame.format.name != "yuv420p" else frame.to_ndarray()
                               for frame in new_frames])

            if blk_start == self.prev_start:
                fields = self.reverse_mapping_head

                try:
                    M = self.reverse_matrix_blended_head

                except numpy.linalg.LinAlgError:
                    M = fields

            elif blk_start == self.prev_end - self.old_blksize_tail:
                fields = self.reverse_mapping_tail

                try:
                    M = self.reverse_matrix_blended_tail

                except numpy.linalg.LinAlgError:
                    M = fields

            else:
                M = self.reverse_matrix_blended
                fields = self.reverse_mapping

            for newframe in self._pullupBlock(frames, frames_yuv, M, dest_index, fields):
                yield newframe

            del frames[:next_start - blk_start]
            del frames_yuv[:next_start - blk_start]
            blk_start = next_start
            next_start = min(next_start + self.old_blksize, self.prev_end)

    def processFrames(self, iterable, prev_start):
        if self.pulldown is None:
            for frame in self._copyFrames(iterable, prev_start):
                yield frame

        else:
            for frame in self._pullupFrames(iterable, prev_start):
                yield frame


class ZonedPullup(zoned.ZonedFilter):
    zoneclass = Zone

    def __init__(self, zones=[], time_base=QQ(1, 1000), start_pts_time=0, prev=None, next=None, notify_input=None, notify_output=None):
        super().__init__(zones=zones, prev=prev, next=next,
                         notify_input=notify_input, notify_output=notify_output)
        self.time_base = time_base
        self._start_pts_time = start_pts_time
        self._columns = None

    def __getstate__(self):
        state = OrderedDict()

        if self.time_base:
            state["time_base"] = self.time_base

        if self.start_pts_time:
            state["start_pts_time"] = self.start_pts_time

        return state

    def __setstate__(self, state):
        self.time_base = state.get("time_base", QQ(1, 1000))
        self.start_pts_time = state.get("start_pts_time", 0)

    @property
    def time_base(self):
        return self._time_base

    @time_base.setter
    def time_base(self, value):
        self._time_base = value
        self.reset_cache()

    @property
    def start_pts_time(self):
        return self._start_pts_time

    @start_pts_time.setter
    def start_pts_time(self, value):
        self._start_pts_time = value
        self.reset_cache()

    def __str__(self):
        if self is None:
            return "Variable Frame Rate/Detelecine"

        if len(self) == 1:
            return "Variable Frame Rate/Detelecine (1 zone)"

        return "Variable Frame Rate/Detelecine (%d zones)" % len(self)

    @property
    def start_pts_time(self):
        return self._start_pts_time

    @start_pts_time.setter
    def start_pts_time(self, value):
        self._start_pts_time = value
        self.reset_cache()

    def translate_fields(self, n):
        if isinstance(n, int):
            k, zone = self.zoneAt(n)
            return zone.translate_fields(n)

        elif isinstance(n, (list, tuple, range, numpy.ndarray)):
            m = numpy.zeros(n.shape+(2,), dtype=numpy.int0)

            for zone in self:
                filter = (n >= zone.prev_start)*(n < zone.prev_end)
                m[filter] = zone.backtranslate_fields(n[filter])

            return m

    def backtranslate_fields(self, m):
        if isinstance(m, int):
            k, zone = self.zoneAtNew(m)
            return zone.backtranslate_fields(m)

        elif isinstance(m, (list, tuple, range, numpy.ndarray)):
            n = numpy.zeros(m.shape+(2,), dtype=numpy.int0)

            for zone in self:
                filter = (m >= zone.dest_start)*(m < zone.dest_end)
                n[filter] = zone.backtranslate_fields(m[filter])

            return n

    def final_fields(self, n):
        m = self.translate_fields(n)
        #m = self.indexMap_cumulative
        filter = self.next
        while filter is not None:
            mm = m.copy()
            filt = (m >= 0)*(m < filter.framecount)
            if filt.any():
                mm[filt] = filter.indexMap[m[filt]]
                #mm[filt] = filter._translate_index(m[filt])
            filter = filter.next
            m = mm
        return m

    def autoframerate(self):
        while len(self) > 1:
            self.removeZoneAt(self[1].src_start)

        dt = numpy.diff(self.prev.pts)
        n = 0
        fr = None

        while n < len(dt) - 1:
            if abs(dt[n:n+2] - numpy.array([50, 33])).max() <= 1:
                if fr != QQ(24000, 1001):
                    fr = QQ(24000, 1001)
                    if n == 0:
                        self.start.src_fps = fr
                        self.start.pulldown = None

                    else:
                        self.insertZoneAt(n, src_fps=fr)

                n += 2

                while n < len(dt) - 1 and abs(dt[n:n+2] - numpy.array([50, 33])).max() <= 1:
                    n += 2

            elif abs(dt[n] - 33) <= 1:
                if fr != QQ(30000, 1001):
                    fr = QQ(30000, 1001)

                    if n == 0:
                        self.start.src_fps = fr
                        self.start.pulldown = None

                    else:
                        self.insertZoneAt(n, src_fps=fr)

                n += 1

                while n < len(dt) - 1 and abs(dt[n] - 33).max() <= 1:
                    n += 1

            elif fr != QQ(24000, 1001):
                fr = QQ(24000, 1001)

                if n == 0:
                    self.start.src_fps = fr
                    self.start.pulldown = None

                else:
                    self.insertZoneAt(n, src_fps=fr)

                n += 1

            else:
                n += 1

    @cached
    def defaultDuration(self):
        durations = {}

        for zone in self:
            defaultDuration = 1/(zone.dest_fps*self.time_base)

            if defaultDuration in durations:
                durations[defaultDuration] += zone.duration

            else:
                durations[defaultDuration] = zone.duration

        return max(durations.keys(), key=lambda key: durations[key])

    def reset_cache(self, start=0, end=None, reset_children=True):
        del self.defaultDuration
        super().reset_cache(start, end, reset_children)

    def QtTableColumns(self):
        from .qpullup import (FrameRateCheckCol, FrameRateCol, TCPatternCol, TCPatternOffsetCol,
                            YBlendCheckCol, UVBlendCheckCol, FrameRateECol, FrameRateOCol)
        return [
            FrameRateCheckCol(self),
            FrameRateCol(self),
            TCPatternCol(self),
            TCPatternOffsetCol(self),
            YBlendCheckCol(self),
            UVBlendCheckCol(self),
            FrameRateECol(self),
            FrameRateOCol(self)
        ]

    @staticmethod
    def QtDlgClass():
        from .qpullup import QPullup
        #return QPullup
