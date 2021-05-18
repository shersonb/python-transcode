#!/usr/bin/python3
from ..base import BaseVideoFilter
from transcode.util import cached
import numpy


class DropFrames(BaseVideoFilter, set):
    def __init__(self, dropframes=[], prev=None, next=None):
        set.__init__(self, dropframes)
        BaseVideoFilter.__init__(self, prev=prev, next=next)

    @property
    def time_base(self):
        if self.prev is not None:
            return self.prev.time_base

    @time_base.setter
    def time_base(self, value):
        self.reset_cache()

    def copy(self):
        return type(self)(self)

    def __str__(self):
        if self is None:
            return "Drop Frames"
        if len(self) == 1:
            return "Drop Frames (1 dropped frame)"
        return "Drop Frames (%d dropped frames)" % len(self)

    def reset_cache(self, start=0, end=None):
        del self.pts_duration
        del self.prev_dropframes
        super().reset_cache(start, end)

    def add(self, *items):
        set.add(self, *items)

        for item in items:
            self.reset_cache(item, item+1)

    def remove(self, *items):
        set.remove(self, *items)

        for item in items:
            self.reset_cache(item, item+1)

    @cached
    def framecount(self):
        dropcount = len(
            list(filter(
                lambda d: d < self.prev.framecount, self.prev_dropframes)))

        return self.prev.framecount - dropcount

    @cached
    def prev_dropframes(self):
        if len(self) == 0:
            return set()

        n = numpy.int0(sorted(self))
        m = self.prev.cumulativeIndexMap[n]

        return set(m[m >= 0])

    @BaseVideoFilter.indexMap.getter
    def indexMap(self):
        n = numpy.arange(self.prev.framecount)
        results = -numpy.ones(n.shape, dtype=numpy.int0)
        matched = numpy.zeros(n.shape, dtype=bool)

        for k, d in enumerate(sorted(self.prev_dropframes)):
            prefilter = n < d
            arrayfilter = (~matched)*(prefilter)
            results[arrayfilter] = n[arrayfilter] - k
            matched[arrayfilter] = True
            matched[n == d] = True

        results[~matched] = n[~matched] - len(self.prev_dropframes)
        return results

    @BaseVideoFilter.reverseIndexMap.getter
    def reverseIndexMap(self):
        m = numpy.arange(self.framecount)
        results = -numpy.ones(m.shape, dtype=numpy.int0)
        matched = numpy.zeros(m.shape, dtype=bool)

        for k, d in enumerate(sorted(self.prev_dropframes)):
            prefilter = m < d - k
            arrayfilter = (~matched)*(prefilter)
            results[arrayfilter] = m[arrayfilter] + k
            matched[arrayfilter] = True

        results[~matched] = m[~matched] + len(self.prev_dropframes)
        return results

    def _processFrames(self, iterable):
        frame = next(iterable)
        firstpts = frame.pts

        n = self.prev.frameIndexFromPts(firstpts)
        m = self.indexMap[n]

        if n not in self.prev_dropframes:
            frame.pts = self.pts[m]
            yield frame
            m += 1

        for k, frame in enumerate(iterable, n + 1):
            if k in self.prev_dropframes:
                continue

            frame.pts = self.pts[m]
            yield frame
            m += 1

    @BaseVideoFilter.pts_time.getter
    def pts_time(self):
        t0 = self.prev.pts_time[0]
        return numpy.concatenate([[t0], t0 + self.pts_duration.cumsum()[:-1]])

    @cached
    def pts(self):
        return self._calc_pts()

    @cached
    def pts_duration(self):
        durations = numpy.diff(numpy.concatenate(
            [self.prev.pts_time, [self.prev.duration]]))
        filter = numpy.ones(durations.shape, dtype=bool)
        A = numpy.int0([m for m in self.prev_dropframes if m < len(durations)])
        filter[A] = False
        return durations[filter]

    @pts_duration.deleter
    def pts_duration(self):
        del self.pts_time
        del self.duration

    @pts_time.deleter
    def pts_time(self):
        del self.pts

    @cached
    def duration(self):
        t0 = self.prev.pts_time[0]
        return t0 + self.pts_duration.sum()

    def __getstate__(self):
        state = super().__getstate__()
        state["dropframes"] = list(self)
        return state

    def __setstate__(self, state):
        self.clear()
        self.update(state.get("dropframes", []))
        super().__setstate__(state)

    def __hash__(self):
        return BaseVideoFilter.__hash__(self)

    def QtTableColumns(self):
        from .qdropframes import DropFrameCol
        return [DropFrameCol(self)]
