from .video.base import BaseVideoFilter
from .audio.base import BaseAudioFilter
import numpy
from collections import OrderedDict
from itertools import count
from ..util import cached
from ..avarrays import toNDArray, toAFrame

class Slice(BaseVideoFilter, BaseAudioFilter):
    def __init__(self, startpts=0, endpts=None, **kwargs):
        self.startpts = startpts
        self.endpts = endpts
        super().__init__(**kwargs)

    @cached
    def prev_start(self):
        return self.prev.frameIndexFromPts((self.startpts - 0.0005)/self.prev.time_base, "+")

    @cached
    def prev_end(self):
        if self.endpts is not None:
            return self.prev.frameIndexFromPts((self.endpts - 0.0005)/self.prev.time_base, "+")

        return self.prev.framecount

    @cached
    def pts_time(self):
        return self.prev.pts_time[self.prev_start:self.prev_end] - self.startpts

    @cached
    def pts(self):
        return numpy.int0(self.pts_time/self.time_base)

    @cached
    def duration(self):
        if self.endpts is not None:
            return self.endpts - self.startpts

        return self.prev.duration - self.startpts

    @cached
    def durations(self):
        return self.prev.durations[self.prev_start:self.prev_end]

    @property
    def layout(self):
        if self.prev is not None:
            return self.prev.layout

    @property
    def rate(self):
        if self.prev is not None:
            return self.prev.rate

    @property
    def time_base(self):
        if self.prev is not None:
            return self.prev.time_base

    @cached
    def framecount(self):
        return len(self.pts)

    @cached
    def indexMap(self):
        return 

    @cached
    def reverseIndexMap(self):
        return numpy.arange(self.prev_start, self.prev_end, dtype=numpy.int0)

    @property
    def prev(self):
        return self._prev

    @prev.setter
    def prev(self, value):
        self._prev = value

        if len(self) and self.start is not None:
            self.start.prev = value

    @property
    def prev(self):
        return self._prev

    @prev.setter
    def prev(self, value):
        self._prev = value
        self.reset_cache()

    #def QTableColumns(self):
        #cols = []
        #for filt in self:
            #if hasattr(filt, "QTableColumns") and callable(filt.QTableColumns):
                #cols.extend(filt.QTableColumns())
        #return cols


    def iterFrames(self, start=0, end=None, whence=None):
        if self.type == "video":
            if whence is None:
                whence = "framenumber"

            if whence == "framenumber":
                N = count(start)
                start = self.prev_start + start

                if end is not None and self.endpts is not None:
                    end = min(self.prev_start + end, self.prev_end)

                else:
                    end = self.prev_end


            elif whence == "pts":
                N = count(self.prev.frameIndexFromPts(start) - self.prev_start)
                start = (self.startpts - 0.0005)/self.prev.time_base + max(start, 0)

                if end is not None and self.endpts is not None:
                    end = min((self.startpts - 0.0005)/self.prev.time_base + end, (self.endpts - 0.0005)/self.prev.time_base)

                elif end is not None:
                    end = (self.startpts - 0.0005)/self.prev.time_base + end

                elif self.endpts is not None:
                    end = (self.endpts - 0.0005)/self.prev.time_base

                else:
                    end = None


            elif whence == "seconds":
                N = count(self.prev.frameIndexFromPts(start/self.prev.time_base) - self.prev_start)
                start = self.startpts - 0.0005 + max(start, 0)

                if end is not None and self.endpts is not None:
                    end = min(self.startpts - 0.0005 + end, self.endpts - 0.0005)

                elif end is not None:
                    end = self.startpts - 0.0005 + end

                elif self.endpts is not None:
                    end = self.endpts - 0.0005

                else:
                    end = None


            I = self.prev.iterFrames(start, end, whence)
            pts = self.pts

            for n, frame in zip(N, I):
                frame.pts = pts[n]
                yield frame

        elif self.type == "audio":
            if whence is None:
                whence = "seconds"

            if whence == "pts":
                start = self.startpts/self.prev.time_base + max(start, 0)

                if end is not None and self.endpts is not None:
                    end = min(self.startpts/self.prev.time_base + end, self.endpts/self.prev.time_base)

                elif end is not None:
                    end = self.startpts/self.prev.time_base + end

                elif self.endpts is not None:
                    end = self.endpts/self.prev.time_base

                else:
                    end = self.prev.duration/self.prev.time_base


            elif whence == "seconds":
                start = self.startpts + max(start, 0)

                if end is not None and self.endpts is not None:
                    end = min(self.startpts + end, self.endpts)

                elif end is not None:
                    end = self.startpts + end

                elif self.endpts is not None:
                    end = self.endpts

                else:
                    end = self.prev.duration


            I = self.prev.iterFrames(start, end, whence)

            for frame in I:
                if whence == "seconds":
                    n1 = int(numpy.floor((start - frame.pts*frame.time_base)*frame.rate).clip(min=0))
                    n2 = int(numpy.floor((frame.pts*frame.time_base + frame.samples/frame.rate - end)*frame.rate).clip(min=0))

                elif whence == "pts":
                    n1 = int(numpy.floor((start*frame.time_base - frame.pts*frame.time_base)*frame.rate).clip(min=0))
                    n2 = int(numpy.floor((frame.pts*frame.time_base + frame.samples/frame.rate - end*frame.time_base)*frame.rate).clip(min=0))

                if n1 or n2:
                    pts = frame.pts
                    tb = frame.time_base
                    r = frame.rate
                    A = toNDArray(frame)[n1 or None:(-n2) or None]

                    if len(A) == 0:
                        continue

                    frame = toAFrame(A, layout=frame.layout.name)
                    frame.rate = r

                    if whence == "seconds":
                        frame.pts = max(pts - int(self.startpts/tb + 0.001), int((start - self.startpts)/tb + 0.001))

                    elif whence == "pts" and pts < start:
                        frame.pts = max(pts - int(self.startpts/tb + 0.001), int(start - self.startpts/tb + 0.001))


                else:
                    frame.pts -= int(self.startpts/self.time_base + 0.001)

                yield frame



    def __reduce__(self):
        return type(self), (), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()

        if self.prev:
            state["prev"] = self.prev

        state["startpts"] = self.startpts
        state["endpts"] = self.endpts
        return state

    def __setstate__(self, state):
        self.prev = state.get("prev")
        self.startpts = state.get("startpts", 0)
        self.endpts = state.get("endpts")
