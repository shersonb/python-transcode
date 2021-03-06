from ...util import cached, search, ValidationException
from ..base import BaseFilter, notifyIterate
import numpy
from itertools import count


class InvalidType(ValidationException):
    pass


class BaseVideoFilter(BaseFilter):
    allowedtypes = ("video",)

    @property
    def sar(self):
        if self.prev is not None:
            return self.prev.sar

    @property
    def width(self):
        if self.prev is not None:
            return self.prev.width

    @property
    def height(self):
        if self.prev is not None:
            return self.prev.height

    @cached
    def pts_time(self):
        if self.prev is not None:
            return self.prev.pts_time

    @pts_time.deleter
    def pts_time(self):
        del self.pts

    @cached
    def pts(self):
        return self._prev_pts()

    def _calc_pts(self):
        if self.time_base is not None:
            return numpy.int0(self.pts_time/float(self.time_base) + 0.0001)

    def _prev_pts(self):
        if self.prev is not None:
            return self.prev.pts

    @property
    def defaultDuration(self):
        if self.prev and self.prev.defaultDuration is not None:
            return self.prev.defaultDuration*self.prev.time_base/self.time_base

    @property
    def rate(self):
        if self.defaultDuration and self.time_base:
            return 1/(self.time_base*self.defaultDuration)

    @property
    def format(self):
        if self.prev:
            return self.prev.format

    def reset_cache(self, start=0, end=None):
        try:
            del self.framecount

        except AttributeError:
            pass

        try:
            del self.durations

        except AttributeError:
            pass

        try:
            del self.indexMap

        except AttributeError:
            pass

        try:
            del self.reverseIndexMap

        except AttributeError:
            pass

        try:
            del self.pts

        except AttributeError:
            pass

        try:
            del self.pts_time

        except AttributeError:
            pass

        try:
            del self.keyframes

        except AttributeError:
            pass

        super().reset_cache(start, end)

    @cached
    def framecount(self):
        if self.prev is not None and self.prev.framecount is not None:
            for k in count(self.prev.framecount - 1, -1):
                n = self.indexMap[k]
                if n not in (None, -1):
                    return n + 1

    @framecount.deleter
    def framecount(self):
        del self.duration

    @cached
    def duration(self):
        prev = self.prev

        if prev is not None:
            return prev.duration

    @cached
    def durations(self):
        if self.framecount is not None and self.defaultDuration is not None:
            return (numpy.ones(self.framecount, dtype=numpy.int0)
                    * int(self.defaultDuration))

    def frameIndexFromPts(self, pts, dir="+"):
        return search(self.pts, pts, dir)

    def frameIndexFromPtsTime(self, pts_time, dir="+"):
        return search(self.pts_time, pts_time, dir)

    @cached
    def cumulativeIndexMap(self):
        if (hasattr(self.prev, "cumulativeIndexMap")
                and self.prev.cumulativeIndexMap is not None):
            n = self.prev.cumulativeIndexMap

        elif self.prev is not None and self.prev.framecount is not None:
            n = numpy.arange(self.prev.framecount)

        else:
            return

        nonneg = n >= 0
        results = -numpy.ones(n.shape, dtype=numpy.int0)
        results[nonneg] = self.indexMap[n[nonneg]]

        return results

    @cached
    def cumulativeIndexReverseMap(self):
        n = self.reverseIndexMap
        if (hasattr(self.prev, "cumulativeIndexReverseMap")
                and self.prev.cumulativeIndexReverseMap is not None):
            n = self.prev.cumulativeIndexReverseMap[n]

        return n

    @cached
    def indexMap(self):
        if self.prev is not None and self.prev.framecount is not None:
            return numpy.arange(self.prev.framecount)

    @cached
    def reverseIndexMap(self):
        if self.prev is not None and self.prev.framecount is not None:
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

                except Exception:
                    end = None

        elif whence == "seconds":
            start = self.frameIndexFromPts(start/self.time_base)

            if end is not None:
                try:
                    end = self.frameIndexFromPts(end/self.time_base)

                except Exception:
                    end = None

        prev_start = self.reverseIndexMap[start]

        if end is not None and end < self.framecount:
            prev_end = self.reverseIndexMap[end]

        else:
            prev_end = None

        iterable = self.prev.iterFrames(
            prev_start, prev_end, whence="framenumber")

        for frame in self.processFrames(iterable):
            k = self.frameIndexFromPts(frame.pts)

            if k < start:
                continue

            if end is not None and k >= end:
                break

            yield frame

    @property
    def prev_keyframes(self):
        prev = self.prev

        if isinstance(prev, BaseVideoFilter):
            return prev.keyframes

        return set()

    @cached
    def keyframes(self):
        prev = self.prev_keyframes
        kf = set(self.indexMap[numpy.int0(list(prev))])
        return self.new_keyframes.union(kf)

    @property
    def new_keyframes(self):
        return set()

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

    def QtTableColumns(self):
        return []

    def validate(self):
        exceptions = BaseFilter.validate(self)

        if self.prev is not None and self.prev.type != "video":
            return [InvalidType("Source is not video.", self)] + exceptions

        return exceptions
