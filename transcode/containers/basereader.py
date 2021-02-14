import av
import threading
import os
from ..util import cached, search, WorkaheadIterator
from collections import OrderedDict
import numpy
from av import VideoFrame
import gc


class Track(object):
    from copy import deepcopy as copy
    name = None
    language = None

    def __init__(self):
        self.container = None
        self.pts = None
        self._lock = threading.Lock()
        self._frame_cache = {}
        self._gop_read_conditions = {}
        self._cache_order = []

    @property
    def track_index(self):
        return self.container.tracks.index(self)

    def frameIndexFromPts(self, pts, dir="+"):
        return search(self.pts, pts, dir)

    def frameIndexFromPtsTime(self, pts_time, dir="+"):
        return search(self.pts_time, pts_time, dir)

    def __reduce__(self):
        state = self.__getstate__()

        if state:
            return type(self), (), state

        return type(self), ()

    def __getstate__(self):
        state = OrderedDict()
        state["pts"] = self.pts
        return state

    def __setstate__(self, state):
        self.pts = state.get("pts")

    def keyIndexFromPts(self, pts, dir="-"):
        k = self.frameIndexFromPts(pts, "-" if self.type == "audio" else "+")
        pts = self.pts[k]
        return search(self.index[:, 0], pts, dir)

    @property
    def framecount(self):
        return len(self.pts)

    @cached
    def pts_time(self):
        return self.pts*float(self.time_base)

    @property
    def format(self):
        return

    @property
    def bitdepth(self):
        return

    @property
    def width(self):
        return

    @property
    def height(self):
        return

    @property
    def rate(self):
        return

    def iterFrames(self, start=0, end=None, whence="pts"):
        if self.type == "video":
            return self._iterVideoFrames(start, end, whence)

        if self.type == "audio":
            return self._iterAudioFrames(start, end, whence)

        raise ValueError(f"Unsupported media type: {self.type}")

    def _iterVideoFrames(self, start=0, end=None, whence="pts"):
        if whence == "framenumber":
            startindex = start
            startpts = self.pts[start]
            endindex = end and min(end, len(self.pts))

            try:
                endpts = end and self.pts[endindex]

            except IndexError:
                endpts = None

        elif whence == "pts":
            if start >= self.pts[0]:
                startindex = self.frameIndexFromPts(
                    start, "-" if self.type is "audio" else "+")

            else:
                startindex = 0

            startpts = self.pts[startindex]

            try:
                endindex = end and self.frameIndexFromPts(end)
                endpts = end and self.pts[endindex]

            except IndexError:
                endindex = None
                endpts = None

        elif whence == "seconds":
            if start/self.time_base >= self.pts[0]:
                startindex = self.frameIndexFromPts(
                    start/self.time_base, "-" if self.type is "audio" else "+")

            else:
                startindex = 0

            startpts = start/self.time_base

            try:
                endindex = end and self.frameIndexFromPts(end/self.time_base)
                endpts = end and self.pts[endindex]

            except IndexError:
                endindex = None
                endpts = None

        if isinstance(self.index, numpy.ndarray) and self.index.ndim == 2 \
                and self.index.size and startpts >= self.index[0, 0]:
            key_index = self.keyIndexFromPts(startpts)

        else:
            key_index = 0

        for n in range(key_index, len(self.index)):
            for frame in self._iterGOP(n):
                if frame.pts < startpts:
                    continue

                if endpts is not None and frame.pts >= endpts:
                    raise StopIteration

                yield frame

    def _iterAudioFrames(self, start=0, end=None, whence="pts"):
        if whence == "framenumber":
            startindex = start
            startpts = self.pts[start]
            endindex = end and min(end, len(self.pts))

            try:
                endpts = end and self.pts[endindex]

            except IndexError:
                endpts = None

        elif whence == "pts":
            if start >= self.pts[0]:
                startindex = self.frameIndexFromPts(
                    start, "-" if self.type is "audio" else "+")

            else:
                startindex = 0

            startpts = self.pts[startindex]

            try:
                endindex = end and self.frameIndexFromPts(end)
                endpts = end and self.pts[endindex]

            except IndexError:
                endindex = None
                endpts = None

        elif whence == "seconds":
            if start/self.time_base + 0.01 >= self.pts[0]:
                startindex = self.frameIndexFromPts(
                    start/self.time_base + 0.01, "-" if self.type is "audio" else "+")

            else:
                startindex = 0

            startpts = start/self.time_base

            try:
                endindex = end and self.frameIndexFromPts(end/self.time_base + 0.01)
                endpts = end and self.pts[endindex]

            except IndexError:
                endindex = None
                endpts = None

        if isinstance(self.index, numpy.ndarray) and self.index.ndim == 2 \
                and self.index.size and startpts >= self.index[0, 0]:
            key_index = self.keyIndexFromPts(startpts)

        else:
            key_index = 0

        key_pts = self.index[key_index, 0]
        index = self.frameIndexFromPts(key_pts)

        packets = self.iterPackets(key_pts)

        if hasattr(self, "defaultDuration") and self.defaultDuration:
            packets = WorkaheadIterator(packets,
                        int(10/self.defaultDuration/self.time_base) + 1)

        else:
            packets = WorkaheadIterator(packets)

        decoder = av.CodecContext.create(self.codec, "r")

        iterpts1 = iter(self.pts[index:])
        iterpts2 = iter(self.pts[index+1:])

        try:
            if self.extradata:
                decoder.extradata = self.extradata

            framesdelivered = 0

            for packet in packets:
                avpacket = av.Packet(packet.data)
                avpacket.pts = packet.pts
                avpacket.time_base = self.time_base

                for frame, pts1, pts2 in zip(decoder.decode(avpacket), iterpts1, iterpts2):
                    if self.type == "audio":
                        pts1 = int(int(
                            (pts1 - self.pts[0])/self.defaultDuration + 0.5)*self.defaultDuration + 0.5) + self.pts[0]
                        pts2 = int(int(
                            (pts2 - self.pts[0])/self.defaultDuration + 0.5)*self.defaultDuration + 0.5) + self.pts[0]

                    if pts2 <= startpts:
                        continue

                    if endpts is not None and pts1 >= endpts:
                        raise StopIteration

                    framesdelivered += 1
                    frame.pts = pts1
                    frame.time_base = self.time_base

                    yield frame

            for frame, pts in zip(decoder.decode(), iterpts1):
                if pts < startpts:
                    continue

                if endpts is not None and pts >= endpts:
                    raise StopIteration

                framesdelivered += 1
                frame.pts = pts
                frame.time_base = self.time_base
                yield frame

        finally:
            decoder.close()

    def _iterGOP(self, n, start=0, end=None):
        with self._lock:
            if n in self._frame_cache:
                frames = self._frame_cache[n]
                c = self._gop_read_conditions.get(n)

                if n in self._cache_order:
                    self._cache_order.remove(n)

                self._cache_order.insert(0, n)

            else:
                frames = self._frame_cache[n] = []
                c = self._gop_read_conditions[n] = threading.Condition(
                    self._lock)
                self._cache_order.insert(0, n)
                t = threading.Thread(
                    target=self._decodeGOP, args=(n, frames, c))
                t.start()

                while len(self._cache_order) > 10:
                    m = self._cache_order.pop()

                    if m in self._gop_read_conditions:
                        del self._gop_read_conditions[m]

                    if m in self._frame_cache:
                        del self._frame_cache[m]

                gc.collect()

        i = start

        while end is None or i < end:
            if c is not None:
                with c:
                    while len(frames) <= i and n in self._gop_read_conditions:
                        c.wait()

            if i >= len(frames):
                break

            (A, fmt, pict_type, pts) = frames[i]
            frame = VideoFrame.from_ndarray(A, fmt)
            frame.pts = pts
            frame.pict_type = pict_type
            frame.time_base = self.time_base
            yield frame

            i += 1

    def _decodeGOP(self, n, frames, c):
        key_pts = self.index[n, 0]
        index = self.frameIndexFromPts(key_pts)

        if n < len(self.index) - 1:
            next_key_pts = self.index[n+1, 0]
            next_key_index = self.frameIndexFromPts(next_key_pts)
            last_pts = self.pts[next_key_index-1]

        else:
            last_pts = None

        packets = self.iterPackets(key_pts)
        iterpts = iter(self.pts[index:])

        decoder = av.CodecContext.create(self.codec, "r")

        try:
            if self.extradata:
                decoder.extradata = self.extradata

            for packet in packets:
                avpacket = av.Packet(packet.data)
                avpacket.pts = packet.pts
                avpacket.time_base = self.time_base

                for frame, pts in zip(decoder.decode(avpacket), iterpts):
                    if self.type == "audio":
                        pts = int(int(
                            (pts - self.pts[0])/self.defaultDuration + 0.5)*self.defaultDuration + 0.5) + self.pts[0]

                    frame.pts = pts

                    if self.type == "video":
                        frame.pict_type = 0

                    with c:
                        frames.append(
                            (frame.to_ndarray(), frame.format.name, frame.pict_type.name, frame.pts))
                        c.notifyAll()

                    if last_pts is not None and pts >= last_pts:
                        return

            for frame, pts in zip(decoder.decode(), iterpts):
                if self.type == "audio":
                    pts = int(int(
                        (pts - self.pts[0])/self.defaultDuration + 0.5)*self.defaultDuration + 0.5) + self.pts[0]

                frame.pts = pts
                frame.time_base = self.time_base

                if self.type == "video":
                    frame.pict_type = 0

                with c:
                    frames.append(
                        (frame.to_ndarray(), frame.format.name, frame.pict_type.name, frame.pts))
                    c.notifyAll()

                if last_pts is not None and pts >= last_pts:
                    return

        finally:
            decoder.close()

            with c:
                if n in self._gop_read_conditions:
                    del self._gop_read_conditions[n]

                c.notifyAll()

    @property
    def duration(self):
        if self.type == "audio":
            return (self.pts[0] + self.pts.size*self.defaultDuration)*self.time_base

        return (self.pts[-1] + self.durations[-1])*self.time_base

    @property
    def avgfps(self):
        return self.framecount/self.duration

    @property
    def defaultDuration(self):
        return None


class BaseReader(object):
    from copy import deepcopy as copy

    trackclass = Track

    def __init__(self, inputpath, tracks=None, config=None):
        self.inputpath = inputpath
        self.config = config
        self._open()

        if tracks is not None:
            self.tracks = tracks

        else:
            self._populatetracks()
            #self.tracks = []
            # self.scan()

    def _open(self):
        raise NotImplementedError(
            f"{self.__class__.__name__}._open not implemented.")

    def _populatetracks(self):
        raise NotImplementedError(
            f"{self.__class__.__name__}._populatetracks not implemented.")

    def __reduce__(self):
        state = self.__getstate__()
        return self.__class__, (self.inputpath,), state, iter(self.tracks)

    def __getstate__(self):
        state = OrderedDict()
        #state["inputpath"] = self.inputpath
        #state["tracks"] = self.tracks
        return state

    def __setstate__(self, state):
        pass

    def append(self, track):
        if track.container is not None and track.container is not self:
            raise ValueError

        track.container = self
        self.tracks.append(track)

    def insert(self, index, track):
        self.tracks.insert(index, track)

    def extend(self, tracks):
        for track in tracks:
            if track.container is not None and track.container is not self:
                raise ValueError

            track.container = self

        self.tracks.extend(tracks)

    def clear(self):
        self.tracks.clear()

    @property
    def inputpathrel(self):
        """Input file path relative to config path."""
        if self.config:
            relpath = os.path.relpath(self.inputpath, self.config.workingdir)

            if relpath.startswith("../"):
                return self.inputpath

            else:
                return relpath

        return self.inputpath

    @inputpathrel.setter
    def inputpathrel(self, value):
        if self.config:
            self.inputpath = os.path.join(self.config.workingdir, value)

        else:
            self.inputpath = value

    @property
    def inputpathabs(self):
        """Input file absolute path."""
        return os.path.abspath(self.inputpath)
