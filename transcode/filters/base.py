from ..util import cached, search, llist, WeakRefProperty, ValidationException, SourceError
from ..containers.basereader import BaseReader, Track
import threading
import numpy
from collections import OrderedDict
from itertools import count
from copy import deepcopy
import weakref


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
    allowedtypes = ("audio", "video")

    @property
    def __name__(self):
        return self.__class__.__name__

    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls)
        self._source = None
        self._prev = None
        self.next = None
        self._parent = None
        self._monitors = {}
        return self

    def __init__(self, source=None, prev=None, next=None, parent=None,
                 name=None, notify_input=None, notify_output=None):
        self.parent = parent

        try:
            self.source = source

        except AttributeError:
            pass

        self.next = next
        self.prev = prev
        self.name = name
        self.notify_input = notify_input
        self.notify_output = notify_output
        self.lock = threading.RLock()

    def addMonitor(self, mon):
        self._monitors[id(mon)] = weakref.ref(mon)

        if isinstance(mon, BaseFilter):
            mon.reset_cache()

    def removeMonitor(self, mon):
        i = id(mon)

        if i in self._monitors and self._monitors[i]() is mon:
            del self._monitors[i]

    @property
    def source(self):
        if isinstance(self.parent, FilterChain):
            return self.parent.prev

        return self._source

    @source.setter
    def source(self, value):
        if isinstance(self.parent, FilterChain):
            raise ValueError(
                f"'source' property is read-only for FilterChain members.")

        oldsource = self._source
        self._source = value

        if isinstance(value, BaseFilter):
            value.addMonitor(self)

        if isinstance(oldsource, BaseFilter) and oldsource not in (self._prev, self._source):
            oldsource.removeMonitor(self)

    @WeakRefProperty
    def source(self, value):
        if isinstance(self.parent, FilterChain):
            return self.parent.prev

        return value

    @source.setter
    def source(self, value):
        if isinstance(self.parent, FilterChain):
            raise ValueError(
                f"'source' property is read-only for FilterChain members.")

        oldsource = self.source

        if isinstance(value, BaseFilter):
            value.addMonitor(self)

        if isinstance(oldsource, BaseFilter) and oldsource is not self._prev:
            oldsource.removeMonitor(self)

        return value

    @WeakRefProperty
    def prev(self, value):
        if isinstance(self._source, weakref.ref):
            source = self._source()

        else:
            source = self._source

        parent = self.parent

        if isinstance(parent, BaseFilter):
            return value or source or self.parent.prev

        return value or source

    @prev.setter
    def prev(self, value):
        oldprev = self._prev() if isinstance(self._prev, weakref.ref) else None

        if isinstance(value, BaseFilter):
            value.addMonitor(self)

        if isinstance(oldprev, BaseFilter) and oldprev is not self._source:
            oldprev.removeMonitor(self)

        return value

    def reset_cache(self, start=0, end=None):
        try:
            del self.duration

        except AttributeError:
            pass

        for i, ref in list(self._monitors.items()):
            mon = ref()

            if mon is None: # Filter has been deallocated, removed from monitors.
                del self._monitors[i]

            elif isinstance(mon, BaseFilter):
                mon.reset_cache(start, end)

    def isValidSource(self, source):
        if source.type not in self.allowedtypes:
            return False

        if self is source:
            return False

        if isinstance(source, BaseFilter) and self in source.dependencies:
            return False

        return True

    def __reduce__(self):
        return type(self), (), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()

        if self.name is not None:
            state["name"] = self.name

        try:
            if isinstance(self._source, weakref.ref):
                source = self._source()

            else:
                source = self._source

            if source is not None:
                state["source"] = self._source()

        except AttributeError:
            pass

        return state

    def __setstate__(self, state):
        if not isinstance(self.parent, FilterChain):
            try:
                self.source = state.get("source", state.get("prev"))

            except AttributeError:
                pass

        self.name = state.get("name")

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
            if "source" in state:
                source = state.pop("source")
                newstate = deepcopy(state, memo)
                newstate["source"] = source

            else:
                newstate = deepcopy(state, memo)

            new.__setstate__(newstate)

        if items is not None:
            new.extend(deepcopy(item, memo) for item in items)

        if dictitems is not None:
            new.update(deepcopy((key, value), memo)
                       for (key, value) in dictitems)

        return new

    @property
    def dependencies(self):
        if isinstance(self.prev, BaseFilter):
            return self.prev.dependencies.union({self.prev})

        if isinstance(self.prev, Track) and self.prev.container is not None:
            return {self.prev, self.prev.container}

        return set()

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

    @cached
    def duration(self):
        if self.prev is not None:
            return self.prev.duration

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

    def frameIndexFromPtsTime(self, pts_time, dir="+"):
        return search(self.pts_time, pts_time + self.time_base/2, dir)

    @cached
    def cumulativeIndexMap(self):
        if hasattr(self._prev, "cumulativeIndexMap"):
            n = self._prev.cumulativeIndexMap

        else:
            n = numpy.arange(self.prev.framecount)

        nonneg = n >= 0
        results = -numpy.ones(n.shape, dtype=numpy.int0)
        results[nonneg] = self.indexMap[n[nonneg]]

        return results

    @cached
    def cumulativeIndexReverseMap(self):
        n = self.reverseIndexMap

        if hasattr(self._prev, "cumulativeIndexReverseMap"):
            n = self._prev.cumulativeIndexReverseMap[n]

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
    def keyframes(self):
        if len(self):
            return self.end.keyframes

        prev = self.prev

        if isinstance(prev, BaseFilter):
            return prev.keyframes

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

    @classmethod
    def hasQtDlg(cls):
        from PyQt5.QtWidgets import QWidget
        return hasattr(cls, "QtDlgClass") and \
            callable(cls.QtDlgClass) and \
            isinstance(cls.QtDlgClass(), type) and \
            issubclass(cls.QtDlgClass(), QWidget)

    @classmethod
    def QtInitialize(cls, parent=None):
        if cls.hasQtDlg():
            return cls.QtDlgClass()(parent)

    def QtDlg(self, parent=None):
        dlg = self.QtInitialize(parent)
        dlg.setFilter(self)
        return dlg

    def removeDependency(self, dependency):
        if isinstance(dependency, BaseReader) and self.source in dependency.tracks:
            self.source = None

        elif isinstance(dependency, BaseFilter) and self.source is dependency:
            self.source = None

    def __repr__(self):
        return f"<{self.__class__.__name__} filter at 0x{id(self):012x}>"

    def validate(self):
        if self.prev is None:
            return [SourceError("No source provided.", self)]

        return []


class FilterChain(llist, BaseFilter):
    from copy import deepcopy as copy

    def __init__(self, filters=[], **kwargs):
        llist.__init__(self, filters.copy())
        BaseFilter.__init__(self, **kwargs)

        if len(self):
            self.end.addMonitor(self)

    def _exchange_new_old(self, oldstart, newstart, oldend, newend):
        if oldstart is not newstart and isinstance(self.prev, BaseFilter):
            if oldstart is not None:
                self.prev.removeMonitor(oldstart)

            if newstart is not None:
                self.prev.addMonitor(newstart)

        if oldend is not newend:
            if oldend is not None:
                oldend.removeMonitor(self)

            if newend is not None:
                newend.addMonitor(self)

    def _get_start_end(self):
        start = self.start if len(self) else None
        end = self.end if len(self) else None
        return (start, end)

    def __setitem__(self, index, value):
        oldstart, oldend = self._get_start_end()
        super().__setitem__(index, value)
        newstart, newend = self._get_start_end()
        self._exchange_new_old(oldstart, newstart, oldend, newend)

    def __delitem__(self, index):
        item = self[index]
        oldstart, oldend = self._get_start_end()
        super().__delitem__(index)
        newstart, newend = self._get_start_end()
        self._exchange_new_old(oldstart, newstart, oldend, newend)


    def append(self, value):
        oldstart, oldend = self._get_start_end()
        super().append(value)
        newstart, newend = self._get_start_end()
        self._exchange_new_old(oldstart, newstart, oldend, newend)

    def insert(self, index, value):
        oldstart, oldend = self._get_start_end()
        super().insert(index, value)
        newstart, newend = self._get_start_end()
        self._exchange_new_old(oldstart, newstart, oldend, newend)

    def extend(self, values):
        oldstart, oldend = self._get_start_end()
        super().extend(values)
        newstart, newend = self._get_start_end()
        self._exchange_new_old(oldstart, newstart, oldend, newend)

    def clear(self):
        oldstart, oldend = self._get_start_end()
        super().clear()
        self._exchange_new_old(oldstart, None, oldend, None)


    @WeakRefProperty
    def source(self, value):
        if isinstance(self.parent, FilterChain):
            return self.parent.prev

        return value

    @source.setter
    def source(self, value):
        if isinstance(self.parent, FilterChain):
            raise ValueError(
                f"'source' property is read-only for FilterChain members.")

        oldsource = self.source

        if isinstance(value, BaseFilter):
            if len(self):
                value.addMonitor(self.start)

            else:
                value.addMonitor(self)

        if isinstance(oldsource, BaseFilter) and oldsource not in (self._prev, value):
            if len(self):
                oldsource.removeMonitor(self.start)

            else:
                oldsource.removeMonitor(self)

        return value

    def isValidSource(self, other):
        if not super().isValidSource(other):
            return False

        for item in self:
            if not item.isValidSource(other):
                return False

        return True

    def __hash__(self):
        return BaseFilter.__hash__(self)

    @property
    def format(self):
        if self.end is not None:
            return self.end.format

        elif self.prev is not None:
            return self.prev.format

    @property
    def sar(self):
        if self.end is not None:
            return self.end.sar

        elif self.prev is not None:
            return self.prev.sar

    @property
    def defaultDuration(self):
        if self.end is not None:
            return self.end.defaultDuration

        elif self.prev is not None:
            return self.prev.defaultDuration

    @property
    def width(self):
        if self.end is not None:
            return self.end.width

        elif self.prev is not None:
            return self.prev.width

    @property
    def height(self):
        if self.end is not None:
            return self.end.height

        elif self.prev is not None:
            return self.prev.height

    @cached
    def pts_time(self):
        if self.end is not None:
            return self.end.pts_time

        elif self.prev is not None:
            return self.prev.pts_time

    @cached
    def pts(self):
        if self.end is not None:
            return self.end.pts

        elif self.prev is not None:
            return self.prev.pts

    @cached
    def duration(self):
        if self.end is not None:
            return self.end.duration

        elif self.prev is not None:
            return self.prev.duration

    @cached
    def durations(self):
        if self.end is not None:
            return self.end.durations

        elif self.prev is not None:
            return self.prev.durations

    @property
    def layout(self):
        if self.end is not None:
            return self.end.layout

        if self.prev is not None:
            return self.prev.layout

    @property
    def rate(self):
        if self.end is not None:
            return self.end.rate

        if self.prev is not None:
            return self.prev.rate

    @cached
    def framecount(self):
        if self.end is not None:
            return self.end.framecount

        elif self.prev is not None:
            return self.prev.framecount

    @property
    def time_base(self):
        if self.end is not None:
            return self.end.time_base

        elif self.prev is not None:
            return self.prev.time_base

    @property
    def indexMap(self):
        if self.end is not None:
            return self.end.cumulativeIndexMap

        elif self.prev is not None:
            return numpy.arange(0, self.prev.framecount, dtype=numpy.int0)

    @property
    def reverseIndexMap(self):
        if self.end is not None:
            return self.end.cumulativeIndexReverseMap

        elif self.prev is not None:
            return numpy.arange(0, self.prev.framecount, dtype=numpy.int0)

        return self.end.reverseIndexMap

    def reset_cache(self, start=0, end=None):
        del self.cumulativeIndexMap
        del self.cumulativeIndexReverseMap
        del self.pts
        del self.pts_time
        del self.framecount
        del self.durations
        del self.duration
        super().reset_cache(start, end)

    def _processFrames(self, iterable, through=None):
        if isinstance(through, (int, numpy.int0)):
            through = self[through]

        for filter in self:
            iterable = filter.processFrames(iterable)

            if filter is through:
                break

        return iterable

    def processFrames(self, iterable, through=None):
        if callable(self.notify_input):
            iterable = notifyIterate(iterable, self.notify_input)

        iterable = self._processFrames(iterable, through)

        if callable(self.notify_output):
            iterable = notifyIterate(iterable, self.notify_output)

        return iterable

    def iterFrames(self, start=0, end=None, whence="framenumber"):
        if self.end is not None:
            return self.end.iterFrames(start, end, whence)

        elif self.prev is not None:
            return self.prev.iterFrames(start, end, whence)

    @staticmethod
    def QtDlgClass():
        from transcode.pyqtgui.qfilterchain import QFilterChain
        return QFilterChain

    def __getstate__(self):
        return BaseFilter.__getstate__(self)

    def __setstate__(self, state):
        BaseFilter.__setstate__(self, state)

    def __reduce__(self):
        return type(self), (), self.__getstate__(), iter(self)

    def __repr__(self):
        return f"<{self.__class__.__name__} ({len(self)} filters) at 0x{id(self):012x}>"
