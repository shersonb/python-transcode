from transcode.util import llist
from transcode.filters.base import BaseFilter
import numpy

class FilterChain(llist, BaseFilter):
    def __init__(self, filters=[], prev=None):
        llist.__init__(self, filters.copy())
        BaseFilter.__init__(self, prev=prev)

    def append(self, item):
        if len(self) == 0:
            super().append(item)
            item.prev = self.prev

        else:
            super().append(item)

    def extend(self, items):
        if len(self) == 0:
            super().extend(items)

            if len(self):
                self[0].prev = self.prev

        else:
            super().extend(items)

    def insert(self, index, item):
        super().insert(index, item)

        if index == 0:
            item.prev = self.prev

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

    @property
    def pts_time(self):
        if self.end is not None:
            return self.end.pts_time

        elif self.prev is not None:
            return self.prev.pts_time

    @property
    def pts(self):
        if self.end is not None:
            return self.end.pts

        elif self.prev is not None:
            return self.prev.pts

    @property
    def duration(self):
        if self.end is not None:
            return self.end.duration

        elif self.prev is not None:
            return self.prev.duration

    @property
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

    @property
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
            return self.end.reverseIndexMap

        elif self.prev is not None:
            return numpy.arange(0, self.prev.framecount, dtype=numpy.int0)

        return self.end.reverseIndexMap

    @property
    def prev(self):
        return self._prev

    @prev.setter
    def prev(self, value):
        self._prev = value

        if len(self) and self.start is not None:
            self.start.prev = value

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

    #def _calc_duration(self):
        #return self.end.duration

    #def _backtranslate_index(self, m):
        #return self.end.backtranslate_index(m)

    #def _translate_index(self, n):
        #return self.end.translate_index(n)

    #def _calc_framecount(self):
        #return self.end.framecount

    #def QTableColumns(self):
        #cols = []
        #for filt in self:
            #if hasattr(filt, "QTableColumns") and callable(filt.QTableColumns):
                #cols.extend(filt.QTableColumns())
        #return cols

    def __reduce__(self):
        return type(self), (), self.__getstate__(), iter(self)

    def __getstate__(self):
        return dict(prev=self.prev)

    def __setstate__(self, state):
        self.prev = state.get("prev")
