from ..video.base import BaseVideoFilter
from ..audio.base import BaseAudioFilter
from ..base import BaseFilter
import numpy
from collections import OrderedDict
from itertools import count
from transcode.util import cached
from transcode.avarrays import toNDArray, toAFrame, aconvert
from av import VideoFrame
from copy import deepcopy
#from transcode.caching import ObjectWithCache, CachedProperty
#from transcode.caching import CachedProperty as cached


class CrossFade(BaseVideoFilter, BaseAudioFilter):
    allowedtypes = ("audio", "video")

    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls)
        self._source1 = None
        self._source2 = None
        return self

    def __init__(self, source1=None, source2=None, flags=0, **kwargs):

        self.source1 = source1
        self.source2 = source2

        if source1 is not None and source2 is not None:
            if source1.type != source2.type:
                raise ValueError("Both segments must have same type.")

            if self.type == "video" and (source1.width != source2.width or source1.height != source2.height):
                raise ValueError("Both segments must have same size.")

            if self.type == "audio" and (source1.layout != source2.layout):
                raise ValueError("Both segments must have same layout.")

        self.flags = flags
        self._prev_start = None
        self._prev_end = None
        super().__init__(**kwargs)

    @property
    def source1(self):
        return self._source1

    @source1.setter
    def source1(self, value):
        oldsource = self._source1
        self._source1 = value

        if isinstance(value, BaseFilter):
            value.addMonitor(self)
            #self.subscribeTo(value)

        if isinstance(oldsource, BaseFilter) and oldsource not in (self._prev, self._source):
            oldsource.removeMonitor(self)
            #self.unsubscribeFrom(oldsource)

    @property
    def source2(self):
        return self._source2

    @source2.setter
    def source2(self, value):
        oldsource = self._source2
        self._source2 = value

        if isinstance(value, BaseFilter):
            value.addMonitor(self)
            #self.subscribeTo(value)

        if isinstance(oldsource, BaseFilter) and oldsource not in (self._prev, self._source):
            oldsource.removeMonitor(self)
            #self.unsubscribeFrom(oldsource)

    def __getstate__(self):
        state = OrderedDict()

        if self.name:
            state["name"] = self.name

        state = OrderedDict()
        state["source1"] = self.source1
        state["source2"] = self.source2
        state["flags"] = self.flags

        return state

    def __setstate__(self, state):
        self.source1 = state.get("source1")
        self.source2 = state.get("source2")
        self.flags = state.get("flags")
        self.name = state.get("name")

    def __deepcopy__(self, memo):
        cls, args, state = self.__reduce__()
        new = cls(*deepcopy(args, memo))

        source1 = state.pop("source1", None)
        source2 = state.pop("source2", None)

        newstate = deepcopy(state, memo)

        newstate["source1"] = source1
        newstate["source2"] = source2

        new.__setstate__(newstate)
        return new

    @property
    def format(self):
        if self.type == "video":
            return "rgb24"

        elif self.type == "audio":
            return "fltp"

    @property
    def dependencies(self):
        dependencies = {self.source1, self.source2}

        if isinstance(self.source1, BaseFilter):
            dependencies.update(self.source1.dependencies)

        if isinstance(self.source2, BaseFilter):
            dependencies.update(self.source2.dependencies)

        return dependencies

    @property
    def pts_time(self):
        if self.source1 is not None:
            return self.source1.pts_time

        if self.source2 is not None:
            return self.source2.pts_time

    @property
    def pts(self):
        if self.source1 is not None:
            return self.source1.pts

        if self.source2 is not None:
            return self.source2.pts

    @pts_time.deleter
    def pts_time(self):
        pass

    @cached
    def duration(self):
        if self.source1 is not None and self.source2 is not None:
            return min(self.source1.duration, self.source2.duration)

        if self.source1 is not None:
            return self.source1.duration

        if self.source2 is not None:
            return self.source2.duration

    @property
    def type(self):
        if self.source1 is not None:
            return self.source1.type

        if self.source2 is not None:
            return self.source2.type

    @property
    def rate(self):
        if self.source1 is not None:
            return self.source1.rate

        if self.source2 is not None:
            return self.source2.rate

    @property
    def channels(self):
        if self.source1 is not None:
            return self.source1.channels

        if self.source2 is not None:
            return self.source2.channels

    @property
    def layout(self):
        if self.source1 is not None:
            return self.source1.layout

        if self.source2 is not None:
            return self.source2.layout

    @property
    def sar(self):
        if self.source1 is not None:
            return self.source1.sar

        if self.source2 is not None:
            return self.source2.sar

    @property
    def height(self):
        if self.source1 is not None:
            return self.source1.height

        if self.source2 is not None:
            return self.source2.height

    @property
    def width(self):
        if self.source1 is not None:
            return self.source1.width

        if self.source2 is not None:
            return self.source2.width

    @cached
    def prev_start(self):
        if self.prev is None:
            return self.src_start

        if hasattr(self.prev, "indexMap"):
            for k in count(self.src_start):
                n = self.prev.indexMap[k]

                if n not in (None, -1):
                    return n
        else:
            return self.src_start

    @cached
    def prev_end(self):
        if self.prev is None:
            return self.src_end

        if self.src_end is None:
            return self.prev.framecount

        if hasattr(self.prev, "indexMap"):
            for k in count(self.src_end):
                n = self.prev.indexMap[k]

                if n not in (None, -1):
                    return n
        else:
            return self.src_end

    @property
    def framecount(self):
        if self.source1 is not None:
            return self.source1.framecount

        if self.source2 is not None:
            return self.source2.framecount

    @framecount.deleter
    def framecount(self):
        return

    @property
    def durations(self):
        if self.source1 is not None:
            return self.source1.durations

        if self.source2 is not None:
            return self.source2.durations

    @durations.deleter
    def durations(self):
        return

    @property
    def time_base(self):
        if self.source1 is not None:
            return self.source1.time_base

        if self.source2 is not None:
            return self.source2.time_base

    def iterFrames(self, start=0, end=None, whence="pts"):
        frames1 = self.source1.iterFrames(start, end, whence)
        frames2 = self.source2.iterFrames(start, end, whence)

        if self.type == "video":
            for frame1, frame2 in zip(frames1, frames2):
                k = self.source1.frameIndexFromPts(frame1.pts)

                A = frame1.to_rgb().to_ndarray()
                B = frame2.to_rgb().to_ndarray()

                if not 1 & self.flags:
                    A = (1 - (k + 1)/(self.framecount + 2))*A

                if not 2 & self.flags:
                    B = ((k + 1)/(self.framecount + 2))*B

                C = numpy.uint8((A + B).clip(max=255) + 0.5).copy(order="C")
                newframe = VideoFrame.from_ndarray(C)
                newframe.time_base = frame1.time_base
                newframe.pts = frame1.pts

                if frame1.pict_type == "I" or frame2.pict_type == "I":
                    newframe.pict_type = "I"

                yield newframe

        elif self.type == "audio":
            AA = numpy.zeros((0, self.source1.channels), dtype=numpy.float32)
            BB = numpy.zeros((0, self.source2.channels), dtype=numpy.float32)
            T = None

            while True:
                while len(AA) < 1536:
                    try:
                        frame1 = next(frames1)

                    except StopIteration:
                        break

                    if T is None:
                        T = frame1.pts*frame1.time_base

                    frame1 = aconvert(frame1, self.format)
                    A = toNDArray(frame1)
                    AA = numpy.concatenate((AA, A))

                while len(BB) < 1536:
                    try:
                        frame2 = next(frames2)

                    except StopIteration:
                        break

                    frame2 = aconvert(frame2, self.format)
                    B = toNDArray(frame2)
                    BB = numpy.concatenate((BB, B))

                N = min(len(AA), len(BB), 1536)

                if N == 0:
                    break

                TT = numpy.arange(T, T + N/self.rate, 1/self.rate)

                if not 1 & self.flags:
                    A = AA[:N]*numpy.cos(T*numpy.pi/2/self.duration)**2

                else:
                    A = AA[:N]

                if not 2 & self.flags:
                    B = BB[:N]*numpy.sin(T*numpy.pi/2/self.duration)**2

                else:
                    B = BB[:N]

                newframe = toAFrame(A + B, layout=self.layout)

                newframe.rate = frame1.rate
                newframe.pts = int(T/frame1.time_base + 0.00001)
                newframe.time_base = frame1.time_base
                yield newframe

                T += N/self.rate
                AA = AA[N:]
                BB = BB[N:]

    @staticmethod
    def QtDlgClass():
        from .qcrossfade import QCrossFade
        return QCrossFade

    def removeDependency(self, dependency):
        if isinstance(dependency, BaseReader) and self.source1 in dependency.tracks:
            self.source1 = None

        elif isinstance(dependency, BaseFilter) and self.source1 is dependency:
            self.source1 = None

        if isinstance(dependency, BaseReader) and self.source2 in dependency.tracks:
            self.source2 = None

        elif isinstance(dependency, BaseFilter) and self.source2 is dependency:
            self.source2 = None

    #def __del__(self):
        #print(f"Deleting {self}")

        #if isinstance(self.source1, BaseFilter):
            #self.source1.removeMonitor(self)

        #if isinstance(self.source2, BaseFilter):
            #self.source2.removeMonitor(self)
