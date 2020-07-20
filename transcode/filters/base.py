import transcode.util
from transcode.util import cached
import transcode.filters.base
import transcode.containers.basereader
from fractions import Fraction as QQ
import threading
import numpy

class BaseFilter(object):
    """
    Base class for filter objects.
    This class also serves as a filter that does nothing.
    """
    from copy import deepcopy as copy

    def __init__(self, prev=None, next=None, parent=None, notify_input=None, notify_output=None):
        self.next = next
        self.prev = prev
        self.parent = parent
        self.notify_input = notify_input
        self.notify_output = notify_output
        self.lock = threading.RLock()

    def __reduce__(self):
        return type(self), (), self.__getstate__()

    @property
    def dependencies(self):
        if isinstance(self.prev, BaseFilter):
            return self.prev.dependencies.union({self.prev})

        return {self.prev}

    def __lt__(self, other):
        if self in other.dependencies:
            return True

        return False

    def __gt__(self, other):
        if other in self.dependencies:
            return True

        return False

    @property
    def type(self):
        if self.prev is not None:
            return self.prev.type

    @property
    def time_base(self):
        try:
            if self._time_base:
                return self._time_base

        except AttributeError:
            if self.prev:
                return self.prev.time_base

    @time_base.setter
    def time_base(self, value):
        self._time_base = value

    @time_base.deleter
    def time_base(self):
        del self._time_base

    @cached
    def pts_time(self):
        if self.prev is not None:
            return self.prev.pts_time

    @pts_time.deleter
    def pts_time(self):
        del self.pts

    @cached
    def pts(self):
        return numpy.int0(self.pts_time/self.time_base)

    @property
    def defaultDuration(self):
        if self.prev:
            return self.prev.defaultDuration

    @property
    def prev(self):
        return self._prev

    @prev.setter
    def prev(self, value):
        self._prev = value
        self.reset_cache()

    @property
    def src(self):
        if isinstance(self.prev, transcode.containers.basereader.Track):
            return self.prev

        elif isinstance(self.prev, BaseVideoFilter):
            return self.prev.src

    @cached
    def duration(self):
        return self.prev.duration

    def reset_cache(self, start=0, end=None):
        del self.framecount
        del self.duration
        del self.indexMap
        del self.reverseIndexMap

        if self.next is not None:
            self.next.reset_cache(start, end)

    @cached
    def framecount(self):
        if self.prev is not None:
            for k in count(self.prev.framecount - 1, -1):
                n = self.indexMap[k]
                if n not in (None, -1):
                    return n + 1

    @framecount.deleter
    def framecount(self):
        del self.duration

    def frameIndexFromPts(self, pts, dir="+"):
        return transcode.util.search(self.pts, pts, dir)

    @cached
    def cumulativeIndexMap(self):
        if hasattr(self.prev, "cumulativeIndexMap"):
            n = self.prev.cumulativeIndexMap

        else:
            n = numpy.arange(self.prev.framecount)

        nonneg = n >= 0
        results = -numpy.ones(n.shape, dtype=numpy.int0)
        results[nonneg] = self.indexMap[n[nonneg]]

        return results

    @cached
    def cumulativeIndexReverseMap(self):
        n = self.reverseIndexMap
        if hasattr(self.prev, "cumulativeIndexReverseMap"):
            n = self.prev.cumulativeIndexReverseMap[n]
        return n

    @cached
    def indexMap(self):
        return numpy.arange(self.prev.framecount)

    @cached
    def reverseIndexMap(self):
        return numpy.arange(self.prev.framecount)

    @indexMap.deleter
    def indexMap(self):
        del self.cumulativeIndexMap

    @reverseIndexMap.deleter
    def reverseIndexMap(self):
        del self.cumulativeIndexReverseMap

    def _processFrames(self, iterable):
        return iterable

    def processFrames(self, iterable):
        if callable(self.notify_input):
            iterable = notifyIterate(iterable, self.notify_input)
        iterable = self._processFrames(iterable)
        if callable(self.notify_output):
            iterable = notifyIterate(iterable, self.notify_output)
        return iterable

    def iterFrames(self, start=0, end=None, whence="framenumber"):
        if whence == "pts":
            start = self.frameIndexFromPts(start)

            if end is not None:
                try:
                    end = self.frameIndexFromPts(end)

                except:
                    end = None

        prev_start = self.reverseIndexMap[start]

        if end is not None and end < self.framecount:
            prev_end = self.reverseIndexMap[end]

        else:
            prev_end = None

        iterable = self.prev.iterFrames(prev_start, prev_end)

        for frame in self.processFrames(iterable):
            k = self.frameIndexFromPts(frame.pts)

            if k < start:
                continue

            if end is not None and k >= end:
                break

            yield frame

    @property
    def keyFrames(self):
        if self.prev:
            return self.prev.keyframes

    def __next__(self):
        with self.lock:
            frame = next(self.prev)
            newframe = self._processFrame(frame)
            self._tell = self.frameIndexFromPts(frame.pts) + 1
            return newframe

    def seek(self, offset):
        with self.lock:
            self.prev.seek(self._backtranslate_index(offset))
            self._tell = offset

    def tell(self):
        with self.lock:
            return self._tell

    def _processFrame(self, frame):
        return frame

