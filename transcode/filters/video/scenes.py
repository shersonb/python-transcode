from transcode.filters.video import zoned
from transcode.filters.video.base import BaseVideoFilter
from transcode.util import cached, numpify
from itertools import count
import numpy
from collections import OrderedDict
import scenedetect
import threading

class Scene(zoned.Zone):
    def __init__(self, src_start, start_pts=None, prev=None, next=None, parent=None):
        super().__init__(src_start=src_start, prev=prev, next=next, parent=parent)
        self.start_pts_time = start_pts

    def __repr__(self):
        return "Scene({self.src_start}, {self.src_end}, {self._framecount})".format(self=self)

    def reset_cache_full(self, notify_parent=True):
        del self.start_pts_time
        super().reset_cache_full(notify_parent=notify_parent)

    @property
    def dest_end(self):
        if self.framecount is not None:
            return self.dest_start + self.framecount

    @property
    def next(self):
        return self._next

    @next.setter
    def next(self, value):
        del self.start_pts_time
        del self.framecount
        self._next = value

    @cached
    def start_pts_time(self):
        if self.parent is not None and self is self.parent.start:
            return 0

        if self.parent is not None and not self.parent.fixpts:
            try:
                return float(self.parent.prev.pts_time[self.prev_start])

            except:
                return

        if self.parent is not None and self.parent.prev_pts_time is not None and self.parent.src_pts_time is not None:
            if self.prev_end == self.prev_start:
                if self.next is not None:
                    return self.next.start_pts_time

                return self.parent.duration

            start_pts_time = self.parent.prev_pts_time[self.prev_start] - \
                (self.parent.pts_time_diff[self.prev_start:self.prev_end]).sum()/(self.prev_end - self.prev_start)
            start_pts_time = int(start_pts_time*120/1.001 + 0.5)*1.001/120
            return start_pts_time

    @property
    def start_pts(self):
        return self.start_pts_time

    @start_pts_time.deleter
    def start_pts_time(self):
        del self.framecount
        del self.pts_time

        if self.prev is not None:
            del self.prev.pts_time_local
            del self.prev.indexMapLocal
            del self.prev.reverseIndexMapLocal
            del self.prev.framecount

    @cached
    def duration(self):
        if self.next is None:
            return self.parent.prev.duration - self.parent.prev_pts_time[self.prev_start]
        else:
            return self.next.start_pts_time - self.start_pts_time

    @cached
    def pts_time_local(self):
        if self.parent is None:
            return

        if not self.parent.fixpts:
            return self.parent.prev.pts_time[self.prev_start:self.prev_end] - self.parent.prev.pts_time[self.prev_start]

        t = self.parent.prev_pts_time[self.prev_start:self.prev_end][:self.framecount] - self.parent.prev_pts_time[self.prev_start]
        return t

    @pts_time_local.deleter
    def pts_time_local(self):
        del self.pts_time
        del self.pts

        if self.parent is not None:
            del self.parent.pts_time

    @cached
    def framecount(self):
        if self.parent.prev is None:
            return

        if not self.parent.fixpts:
            if self.prev_end:
                return int(self.prev_end - self.prev_start)

            return

        if self.next is None:
            if self.prev_framecount is not None:
                return int(self.prev_framecount)

            return

        K = self.parent.index(self.next)
        cutoff = min([zone.start_pts_time for zone in self.parent[K:]]) - 1.001/240
        diff = self.start_pts_time - self.parent.prev.pts_time[self.prev_start]

        for k in count(self.prev_framecount, -1):
            if k == 0 or self.parent.prev.pts_time[self.prev_start + k - 1] + diff < cutoff:
                return int(k)

    @zoned.Zone.indexMapLocal.getter
    def indexMapLocal(self):
        return numpy.concatenate([numpy.arange(self.framecount, dtype=numpy.int0), -numpy.ones(self.prev_framecount - self.framecount, dtype=numpy.int0)])

    def getIterStart(self, start):
        return self.reverseIndexMap[start - self.dest_start]

    def getIterEnd(self, end):
        return self.reverseIndexMap[end - self.dest_start]


    def processFrames(self, iterable, prev_start):
        for k, frame in zip(count(prev_start), iterable):
            j = self.indexMap[k - self.prev_start]

            if j == self.dest_start:
                frame.pict_type = "I"

            if j >= self.dest_end or j < 0:
                break

            try:
                if self.parent.fixpts:
                    frame.pts = self.pts[j - self.dest_start]
            except:
                raise

            yield frame

    def _translate_index_local(self, N):
        if isinstance(N, numpy.ndarray):
            ret = N.copy()
            ret[N >= self.framecount] = -1
            return ret

        elif N >= self.framecount:
            return -1

        return N

class Scenes(zoned.ZonedFilter):
    zoneclass = Scene

    def __str__(self):
        if self is None:
            return "Scenes"

        if len(self) == 1:
            return "Scenes (1 scene)"

        return "Scenes (%d scenes)" % len(self)

    def getinitkwargs(self):
        d = OrderedDict(zones=list(self), fixpts=int(self.fixpts))

        if isinstance(self.stats, numpy.ndarray):
            d["stats"] = self.stats

        return d

    def __init__(self, zones=[], stats=None, fixpts=True, **kwargs):
        if stats is not None:
            self.stats = stats.copy()

        else:
            self.stats = None

        super().__init__(zones, **kwargs)
        self.fixpts = bool(fixpts)

    def __getstate__(self):
        state = OrderedDict()
        state["fixpts"] = self.fixpts

        if self.stats:
            state["stats"] = self.stats

        return state

    def __setstate__(self, state):
        self.fixpts = state.get("fixpts")
        self.stats = state.get("stats")

    @property
    def fixpts(self):
        return self._fixpts

    @fixpts.setter
    def fixpts(self, value):
        self._fixpts = bool(value)
        self.reset_cache()

    def __repr__(self):
        return "<Scene list at %s>" % hex(id(self))

    def reset_cache(self, start=0, end=None, reset_children=True):
        del self.prev_pts_time
        del self.src_pts_time
        super().reset_cache(start, end, reset_children)

    @cached
    def prev_pts_time(self):
        if self.prev is not None:
            return self.prev.pts_time

    @prev_pts_time.deleter
    def prev_pts_time(self):
        del self.pts_time_diff

    @cached
    def src_pts_time(self):
        if self.prev is not None:
            if isinstance(self.prev, BaseVideoFilter):
                n = self.prev.cumulativeIndexReverseMap

                if self.src is not None:
                    return self.src.pts_time[n]

            return self.src.pts_time

    @src_pts_time.deleter
    def src_pts_time(self):
        del self.pts_time_diff

    @cached
    def pts_time_diff(self):
        if self.prev_pts_time is None or self.src_pts_time is None:
            return

        return self.prev_pts_time - self.src_pts_time

    @pts_time_diff.deleter
    def pts_time_diff(self):
        for zone in self:
            zone.reset_cache()

    #def _calc_duration(self):
        #return self.end.start_pts + self.end.duration

    def __next__(self):
        pass

    #@cached
    #def QTableColumns(self):
        #from movie.qscenes import SceneCol, ContentCol, DeltaHueCol, DeltaSatCol, DeltaLumCol
        #col1 = movie.qscenes.SceneCol(self)
        #col2 = movie.qscenes.ContentCol(self)
        #col3 = movie.qscenes.DeltaHueCol(self)
        #col4 = movie.qscenes.DeltaSatCol(self)
        #col5 = movie.qscenes.DeltaLumCol(self)
        #return [col1, col2, col3, col4, col5]

    def analyze(self, start=0, end=None, notify_iter=None, notify_complete=None):
        t = AnalysisThread(self, start, end, notify_iter, notify_complete)
        t.start()
        return t

    @BaseVideoFilter.pts_time.getter
    def pts_time(self):
        if self.fixpts:
            return numpy.concatenate([zone.pts_time for zone in self])
        return self.prev.pts_time

    @BaseVideoFilter.indexMap.getter
    def indexMap(self):
        if self.fixpts:
            return numpy.concatenate([zone.indexMap for zone in self])
        return numpy.arange(self.prev.framecount)

    @BaseVideoFilter.reverseIndexMap.getter
    def reverseIndexMap(self):
        if self.fixpts:
            return numpy.concatenate([zone.reverseIndexMap for zone in self])
        return numpy.arange(self.prev.framecount)

    @property
    def keyFrames(self):
        if self.prev:
            prev = self.prev.keyFrames
            prevadj = set()

            for k in prev:
                try:
                    while self.indexMap[k] < 0:
                        k += 1

                except IndexError:
                    continue

                prevadj.add(self.indexMap[k])

        return prevadj.union({zone.dest_start for zone in self})

class AnalysisThread(threading.Thread):
    def __init__(self, scenes, start, end, notify_iter=None, notify_complete=None):
        self._start = start

        if end is None:
            self._end = scenes.prev.framecount

        else:
            self._end = end

        self.scenes = scenes
        self.frames = scenes.prev.readFrames(start, end)
        self.n = 0
        self.notify_iter = notify_iter
        self.notify_complete = notify_complete
        self.stopped = threading.Event()
        threading.Thread.__init__(self)

    def get(self, *args, **kwargs):
        return 0.0

    def read(self):
        if self.stopped.isSet():
            if callable(self.notify_iter):
                self.notify_iter(-1)

            return (False, None)

        try:
            frame = next(self.frames)

        except StopIteration:
            if callable(self.notify_iter):
                self.notify_iter(-1)

            return (False, None)

        pts = frame.pts
        m, ms = divmod(pts, 60000)
        s = ms/1000
        h, m = divmod(m, 60)

        if frame.format.name != "rgb24":
            frame = frame.to_rgb()

        if callable(self.notify_iter):
            self.notify_iter(self.n)

        self.n += 1
        return (True, frame.to_ndarray())

    def interrupt(self):
        self.stopped.set()

    def run(self):
        try:
            stats = scenedetect.stats_manager.StatsManager()
            scenemgr = scenedetect.SceneManager(stats)
            scenemgr.add_detector(scenedetect.ContentDetector())
            scenemgr.detect_scenes(frame_source=self)

            if self.scenes.stats is None:
                self.scenes.stats = numpy.nan*numpy.zeros((self.scenes.prev.framecount - 1, 4))

            H, W = self.scenes.stats.shape

            if H < self.scenes.prev.framecount - 1 or W < 4:
                newstats = numpy.nan*numpy.zeros((self.scenes.prev.framecount - 1, 4))
                newstats[:H,:W] = self.scenes.stats
                self.scenes.stats = newstats

            for n in range(self._start + 1, self._end):
                self.scenes.stats[n-1] = stats.get_metrics(n - self._start, ["content_val", "delta_hue", "delta_sat", "delta_lum"])

        finally:
            if callable(self.notify_complete):
                self.notify_complete()
