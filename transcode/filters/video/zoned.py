from .base import BaseVideoFilter
from ...util import cached, llist, applyState
import numpy
from itertools import chain, islice, count
import time
from copy import deepcopy
from more_itertools import peekable


class Zone(object):
    from copy import deepcopy as copy

    def __init__(self, src_start, prev=None, next=None, parent=None):
        self._src_start = src_start
        self.parent = parent

        if parent is not None:
            parent.zone_indices.add(src_start)

        self.prev = prev
        self.next = next
        self._prev_start = None
        self._framecount = None
        self._duration = None

    def __repr__(self):
        return "%s(src_start=%s, src_end=%s)" % (type(self).__name__, self.src_start, self.src_end)

    def __reduce__(self):
        state = self.__getstate__()

        if state:
            return type(self), (self.src_start,), state

        return type(self), (self.src_start,)

    def __getstate__(self):
        return None

    def __setstate__(self, state):
        return

    def __deepcopy__(self, memo):
        cls, args, *state = self.__reduce__()
        args, *state = deepcopy((args, *state), memo)
        new = cls(*args)
        applyState(new, *state)

        new.parent = self.parent
        new.prev = self.prev
        new._next = self._next

        return new

    @cached
    def pts_time_local(self):
        return self.parent.prev.pts_time[self.prev_start:self.prev_end] - self.start_pts_time

    @pts_time_local.deleter
    def pts_time_local(self):
        del self.pts_time

    @cached
    def start_pts_time(self):
        return self.parent.prev.pts_time[self.prev_start]

    @cached
    def pts_time(self):
        if self.pts_time_local is None:
            return
        return self.pts_time_local + self.start_pts_time

    @pts_time.deleter
    def pts_time(self):
        del self.pts

    @cached
    def pts(self):
        return numpy.int0(self.pts_time/self.time_base)

    @property
    def next(self):
        if hasattr(self, "_next"):
            return self._next

    @next.setter
    def next(self, value):
        self._next = value

    @next.deleter
    def next(self):
        self.next = None

    @property
    def src_start(self):
        if self.parent is not None and self.parent.start == self:
            return 0

        return self._src_start

    @src_start.setter
    def src_start(self, value):
        if self.parent.start == self and value != 0:
            raise AttributeError(
                "Refusing to set start offset for first zone.")

        if self.parent is not None:
            self.parent.zone_indices.remove(self._src_start)
            self.parent.zone_indices.add(value)

        self._src_start = value
        del self.prev_start

        try:
            del self.start_pts_time

        except AttributeError:
            pass

        if self.prev is not None:
            if self.parent is not None:
                self.parent.reset_cache(self.prev.src_start, self.src_end)

            else:
                self.prev.reset_cache_full(notify_parent=False)
                self.reset_cache_full(notify_parent=False)

        else:
            self.reset_cache_full(notify_parent=False)

    @property
    def src_end(self):
        if self.next is not None:
            return self.next.src_start

        elif self.parent is not None and self.parent.source is not None:
            return self.parent.source.framecount

    @property
    def src_framecount(self):
        return self.src_end - self.src_start

    @property
    def src_pts(self):
        return self.parent.src_pts[self.src_start:self.src_end]

    @cached
    def prev_start(self):
        if self.parent is None:
            return self.src_start

        if hasattr(self.parent.prev, "indexMap"):
            if self.src_start >= len(self.parent.prev.cumulativeIndexMap):
                return self.parent.prev.framecount

            for k in count(self.src_start):
                n = self.parent.prev.cumulativeIndexMap[k]

                if n not in (None, -1):
                    return n

        return self.src_start

    @property
    def prev_end(self):
        if self.next is not None:
            return self.next.prev_start

        elif self.parent is not None and self.parent.prev is not None:
            return self.parent.prev.framecount

    @property
    def prev_framecount(self):
        if self.prev_end is not None:
            return self.prev_end - self.prev_start

    @cached
    def framecount(self):
        return self.prev_framecount

    @property
    def dest_start(self):
        ds = 0
        zone = self.prev

        while zone is not None:
            ds += zone.framecount
            zone = zone.prev

        return ds
        """Why not this?

        return 0 if self.prev is None else self.prev.dest_end

        Because we may exceed maximum recursion depth.
        """

    @property
    def dest_end(self):
        if self.framecount is not None:
            return self.dest_start + self.framecount

    @cached
    def indexMapLocal(self):
        return numpy.arange(self.framecount)

    @indexMapLocal.deleter
    def indexMapLocal(self):
        del self.indexMap

    @cached
    def indexMap(self):
        A = self.indexMapLocal.copy()
        A[A >= 0] += self.dest_start
        return A

    @cached
    def reverseIndexMapLocal(self):
        return numpy.arange(self.framecount)

    @cached
    def reverseIndexMap(self):
        A = self.reverseIndexMapLocal.copy()
        return A + self.prev_start

    @reverseIndexMapLocal.deleter
    def reverseIndexMapLocal(self):
        del self.reverseIndexMap

    @cached
    def duration(self):
        if not self.parent:
            return

        if self.prev_end == self.parent.prev.framecount:
            end_pts = self.parent.prev.duration

        else:
            end_pts = self.parent.prev.pts_time[self.prev_end]

        return end_pts - self.parent.prev.pts_time[self.prev_start]

    @cached
    def start_pts_time(self):
        start_ts = 0
        zone = self.prev

        while zone is not None:
            start_ts += zone.duration
            zone = zone.prev

        return start_ts

    @property
    def time_base(self):
        return self.parent.time_base

    @property
    def end_pts(self):
        return self.start_pts_time + self.duration

    def getIterStart(self, start):
        return self.reverseIndexMap[start - self.dest_start]

    def iterFrames(self, start=0, end=None):
        start = max(start, self.dest_start)
        end = min(end or self.dest_end, self.dest_end)

        if self.parent is not None and self.parent.prev is not None:
            frames = peekable(self.parent.prev.iterFrames(
                start, end, whence="framenumber"))
            prev_start = self.parent.prev.frameIndexFromPts(frames.peek().pts)
            framecount = self.prev_end - prev_start

            for frame in self.processFrames(islice(frames, int(framecount)), prev_start):
                if frame.pts < self.pts[start - self.dest_start]:
                    continue

                if end < self.dest_end and frame.pts < self.pts[end - self.dest_start]:
                    break

                yield frame

    def reset_cache(self):
        del self.prev_start
        del self.pts_time
        del self.indexMap
        del self.reverseIndexMap

    def reset_cache_full(self, notify_parent=True):
        del self.framecount
        del self.duration
        del self.prev_start
        del self.pts_time_local
        del self.indexMapLocal
        del self.reverseIndexMapLocal

        if notify_parent and self.parent is not None:
            self.parent.reset_cache(
                self.src_start, self.src_end, reset_children=False)


class ZonedFilter(llist, BaseVideoFilter):
    zoneclass = None

    def __init__(self, zones=[], prev=None, next=None, notify_input=None, notify_output=None):
        self.zone_indices = set()
        llist.__init__(self, zones)
        BaseVideoFilter.__init__(
            self, prev=prev, next=next, notify_input=notify_input, notify_output=notify_output)

        if not zones:
            self.insertZoneAt(0)

    def __hash__(self):
        return BaseVideoFilter.__hash__(self)

    def __reduce__(self):
        return type(self), (), self.__getstate__(), llist.__iter__(self)

    def __getstate__(self):
        return BaseVideoFilter.__getstate__(self)

    def __setstate__(self, state):
        BaseVideoFilter.__setstate__(self, state)

    def __deepcopy__(self, memo):
        """
        Force CLEAR of self before extend.
        """
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

        new = cls(*(deepcopy(arg, memo) for arg in args))

        if state is not None:
            new.__setstate__(deepcopy(state, memo))

        if items is not None:
            new.clear()
            new.extend(deepcopy(item, memo) for item in items)

        if dictitems is not None:
            new.update(deepcopy(dictitems, memo))

        return new

    def reset_cache(self, start=0, end=None, reset_children=True):
        if len(self) and reset_children:
            J, zone = self.zoneAt(start)
            j = zone.src_start

            while zone is not None and (end is None or zone.src_start < end):
                zone.reset_cache_full(notify_parent=False)
                k = zone.src_end
                zone = zone.next

            while zone is not None:
                zone.reset_cache()
                zone = zone.next

            super().reset_cache(j, k)

        elif len(self):
            J, zone = self.zoneAt(start)
            j = zone.src_start

            if end is not None and end <= self.end.src_start:
                K, zone2 = self.zoneAt(end)
                k = zone2.src_end

            else:
                k = None

            while zone is not None:
                zone.reset_cache()
                zone = zone.next

            super().reset_cache(j, k)

        else:
            super().reset_cache(start, end)

    def _processFrames(self, iterable):
        firstframe = next(iterable)
        firstpts = firstframe.pts  # *firstframe.time_base + 0.0005
        prev_start = self.prev.frameIndexFromPts(firstpts)
        J, start = self.zoneAtPrev(prev_start)

        """
        This iterator prevents start from reading in frames that should
        be processed by the next zone.
        """
        if start.prev_end is not None:
            framecount = start.prev_end - prev_start - 1

            start_iterable = chain(
                [firstframe],
                islice(iterable, int(framecount))
            )

        else:
            start_iterable = chain([firstframe], iterable)

        for frame in start.processFrames(start_iterable, prev_start):
            yield frame

        """
        Finish off start_iterable in case zone does not finish.
        """
        for frame in start_iterable:
            pass

        zone = start.next

        while zone is not None:
            if zone.prev_framecount is not None:
                zone_iterable = islice(iterable, int(zone.prev_framecount))

            else:
                zone_iterable = iterable

            for frame in zone.processFrames(zone_iterable, zone.prev_start):
                yield frame

            for frame in zone_iterable:
                pass

            zone = zone.next

    def iterFrames(self, start=0, end=None, whence="framenumber"):
        if whence == "pts":
            start = self.frameIndexFromPts(start)

            if end is not None:
                try:
                    end = self.frameIndexFromPts(end)

                except:
                    end = None

        if whence == "seconds":
            start = self.frameIndexFromPts(start/self.time_base)

            if end is not None:
                try:
                    end = self.frameIndexFromPts(end/self.time_base)

                except:
                    end = None

        J, start_zone = self.zoneAtNew(start)
        iterstart = start_zone.getIterStart(start)
        iterable = self.prev.iterFrames(iterstart, whence="framenumber")

        for frame in self.processFrames(iterable):
            try:
                k = self.frameIndexFromPts(frame.pts)

            except ValueError:
                raise

            if k < start:
                continue

            if end is not None and k >= end:
                break

            yield frame

    def zoneAt(self, n):
        k = 0
        K = len(self) - 1

        if self[k].src_start <= n and (self[k].src_end is None or n < self[k].src_end):
            return k, self[k]

        if (self[K].src_end is None and self[K].src_start <= n) or self[K].src_start <= n < self[K].src_end:
            return K, self[K]

        while k < K - 1:
            j = (k + K)//2

            if n < self[j].src_start:
                K = j
                continue

            elif n >= self[j].src_end:
                k = j
                continue

            else:
                return j, self[j]

        raise IndexError

    def zoneAtNew(self, m, k=0, K=None):
        if K is None:
            K = len(self) - 1

        if self[k].dest_start <= m < self[k].dest_end:
            return k, self[k]

        if (self[K].dest_end is None and self[K].dest_start <= m) or self[K].dest_start <= m < self[K].dest_end:
            return K, self[K]

        while k < K - 1:
            j = (k + K)//2
            if m < self[j].dest_start:
                K = j
                continue
            elif m >= self[j].dest_end:
                k = j
                continue
            else:
                return j, self[j]

        raise IndexError

    def zoneAtPrev(self, m, k=0, K=None):
        if K is None:
            K = len(self) - 1

        if self[k].prev_start <= m < self[k].prev_end:
            return k, self[k]

        if (self[K].prev_end is None and self[K].prev_start <= m) or self[K].prev_start <= m < self[K].prev_end:
            return K, self[K]

        while k < K - 1:
            j = (k + K)//2

            if m < self[j].prev_start:
                K = j
                continue

            elif m >= self[j].prev_end:
                k = j
                continue

            else:
                return j, self[j]

        raise IndexError

    def insertZoneAt(self, n, *args, **kwargs):
        kwargs["parent"] = self

        try:
            k, zone = self.zoneAt(n)

        except IndexError:
            if n == 0:
                newzone = self.zoneclass(n, *args, **kwargs)
                self.append(newzone)

                if self.next is not None:
                    self.next.reset_cache()

                return 0, newzone

            raise

        if zone.src_start == n:
            return None

        next = zone.next
        kwargs["prev"] = zone
        kwargs["next"] = next
        newzone = self.zoneclass(n, *args, **kwargs)

        if next is not None:
            next.prev = newzone

        zone.next = newzone

        self.insert(k+1, newzone)

        if next is not None:
            self.reset_cache(zone.src_start, next.src_start)

        else:
            self.reset_cache(zone.src_start)

        return k+1, newzone

    @BaseVideoFilter.pts_time.getter
    def pts_time(self):
        return numpy.concatenate([zone.pts_time for zone in self])

    # @pts_time.setter
    # def pts_time(self, value):
        # if self.next is not None:
        # self.next.reset_cache()

    @BaseVideoFilter.indexMap.getter
    def indexMap(self):
        return numpy.concatenate([zone.indexMap for zone in self])

    @BaseVideoFilter.reverseIndexMap.getter
    def reverseIndexMap(self):
        return numpy.concatenate([zone.reverseIndexMap for zone in self])

    # def _translate_index(self, n):
        # if isinstance(n, numpy.ndarray):
        #n_min = n.min()
        #results = numpy.zeros(n.shape, dtype=numpy.int0)
        #matched = numpy.zeros(n.shape, dtype=bool)

        # while not matched.all():
        #n_min = n[~matched].min()
        #k, zone = self.zoneAtPrev(n_min)
        #filter = (n >= zone.prev_start)*(n < zone.prev_end)

        # if not filter.any():
        # continue

        #results[filter] = zone._translate_index(n[filter])
        #matched[filter] = True

        # return results
        # elif n < 0:
        # return -1
        # elif n == self.prev.framecount:
        # return self.framecount
        # else:
        #k, zone = self.zoneAtPrev(n)
        #m = zone._translate_index(n)
        # return m

    # def _backtranslate_index(self, m):
        # if isinstance(m, numpy.ndarray):
        #m = numpy.array(m)
        #m_min = m.min()
        #m_max = m.max()
        #results = numpy.zeros(m.shape, dtype=numpy.int0)
        #matched = numpy.zeros(m.shape, dtype=bool)

        # while not matched.all():
        #m_min = m[~matched].min()
        #k, zone = self.zoneAtNew(m_min)
        #filter = (m >= zone.dest_start)*(m < zone.dest_end)
        # if not filter.any():
        # continue
        #results[filter] = zone._backtranslate_index(m[filter])
        #matched[filter] = True

        # return results
        # else:
        #k, zone = self.zoneAtNew(m)
        # return zone._backtranslate_index(m)

    def removeZoneAt(self, n):
        k, zone = self.zoneAt(n)

        if k == 0:
            raise IndexError("Cowardly refusing to remove starting zone.")

        pz = zone.prev
        nz = zone.next
        pz.next = nz

        if nz is not None:
            nz.prev = pz

        del self[k]

        if nz is not None:
            self.reset_cache(pz.src_start, nz.src_start)

        else:
            self.reset_cache(pz.src_start, None)

    def insert(self, index, zone):
        llist.insert(self, index, zone)
        self.zone_indices.add(zone.src_start)

    def append(self, zone):
        llist.append(self, zone)
        self.zone_indices.add(zone.src_start)

    def extend(self, zones):
        n = len(self)
        llist.extend(self, zones)

        for zone in self[n:]:
            self.zone_indices.add(zone.src_start)

    def __delitem__(self, index):
        zone = self[index]

        if zone.src_start in self.zone_indices:
            self.zone_indices.remove(zone.src_start)

        llist.__delitem__(self, index)

    def remove(self, zone):
        llist.remove(self, zone)

        if zone.src_start in self.zone_indices:
            self.zone_indices.remove(zone.src_start)

    def clear(self):
        self.zone_indices.clear()
        super().clear()

    @cached
    def framecount(self):
        return self.end.dest_end

    @cached
    def duration(self):
        return sum([zone.duration for zone in self])

    @staticmethod
    def QtDlgClass():
        from transcode.pyqtgui.qzones import ZoneDlg
        return ZoneDlg

    # def QtDlg(self, zone=None, offset=None, mode=None, parent=None):
        # if zone is None:
        #zone = self.start

        #dlg = self.QtDlgClass(zone, parent=parent)

        # if mode is None:
        #mode = dlg.modeBox.currentData()

        # if offset is None:
        # if mode == 0:
        #offset = zone.src_start

        # elif mode == 1:
        #offset = zone.prev_start

        # if mode == 2:
        #offset = zone.dest_start

        #index = dlg.modeBox.findData(mode)
        # dlg.modeBox.setCurrentIndex(index)
        # return dlg.exec_()
