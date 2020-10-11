#import ..util
from ..util import cached, search
from ..containers.basereader import Track
from fractions import Fraction as QQ
import threading
import numpy
from collections import OrderedDict
from itertools import count
from copy import deepcopy

def notifyIterate(iterator, func):
    for item in iterator:
        func(item)
        yield item

class CacheResettingProperty(object):
    def __init__(self, attrname):
        self.attrname = attrname
        self._attrname = f"_{attrname}"

    def __get__(self, inst, cls):
        if inst is None:
            return self

        return getattr(inst, self._attrname)

    def __set__(self, inst, value):
        inst.reset_cache()
        setattr(inst, self._attrname, value)

class BaseFilter(object):
    """
    Base class for filter objects.
    This class also serves as a filter that does nothing.
    """

    from copy import deepcopy as copy
    next = None
    prev = CacheResettingProperty("prev")

    @property
    def __name__(self):
        return self.__class__.__name__

    def __init__(self, prev=None, next=None, parent=None, notify_input=None, notify_output=None):
        self.parent = parent
        self.next = next
        self.prev = prev
        self.notify_input = notify_input
        self.notify_output = notify_output
        self.lock = threading.RLock()

    def __reduce__(self):
        return type(self), (), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()

        if self.prev is not None:
            state["prev"] = self.prev

        return state

    def __setstate__(self, state):
        self.prev = state.get("prev")

    def __deepcopy__(self, memo):
        reduced = self.__reduce__()

        if len(reduced) == 2:
            cls, args = reduced
            state = items = dictitems = None

        elif len(reduced) == 3:
            cls, args, state = reduced
            items = dictitems = None

        if len(reduced) == 4:
            cls, args, state, items = reduced
            dictitems = None

        if len(reduced) == 5:
            cls, args, state, items, dictitems = reduced

        new = cls(*args)

        if state is not None:
            if "prev" in state:
                prev = state.pop("prev")
                newstate = deepcopy(state, memo)
                newstate["prev"] = prev

            else:
                newstate = deepcopy(state, memo)

            new.__setstate__(newstate)

        if items is not None:
            new.extend(deepcopy(item, memo) for item in items)

        if dictitems is not None:
            new.update(deepcopy((key, value), memo) for (key, value) in dictitems)

        return new

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

    #@property
    #def prev(self):
        #return self._prev

    #@prev.setter
    #def prev(self, value):
        #self._prev = value
        #self.reset_cache()

    @property
    def src(self):
        if isinstance(self.prev, Track):
            return self.prev

        elif isinstance(self.prev, BaseFilter):
            return self.prev.src

    @cached
    def duration(self):
        return self.prev.duration

    def reset_cache(self, start=0, end=None):
        try:
            del self.duration

        except AttributeError:
            pass

        if self.next is not None:
            self.next.reset_cache(start, end)

        elif isinstance(self.parent, BaseFilter):
            self.parent.reset_cache(start, end)

    @cached
    def framecount(self):
        if self.prev is not None and self.prev.framecount:
            for k in count(self.prev.framecount - 1, -1):
                n = self.indexMap[k]
                if n not in (None, -1):
                    return n + 1

        return 0

    @framecount.deleter
    def framecount(self):
        del self.duration

    def frameIndexFromPts(self, pts, dir="+"):
        return search(self.pts, pts, dir)

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

