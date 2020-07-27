from .video.base import BaseVideoFilter
from .audio.base import BaseAudioFilter
from .base import BaseFilter
import numpy
from collections import OrderedDict
from itertools import count
from ..util import cached
from ..avarrays import toNDArray, toAFrame, aconvert
from fractions import Fraction as QQ

class CrossFade(BaseVideoFilter, BaseAudioFilter):
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

    def __getstate__(self):
        state = OrderedDict()
        state["source1"] = self.source1
        state["source2"] = self.source2
        state["flags"] = self.flags
        return state

    def __setstate__(self, state):
        self.source1 = state.get("source1")
        self.source2 = state.get("source2")
        self.flags = state.get("flags")

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
        return self.source1.pts_time

    @property
    def pts(self):
        return self.source1.pts

    @pts_time.deleter
    def pts_time(self):
        pass

    @cached
    def duration(self):
        return self.source1.duration

    @property
    def type(self):
        return self.source1.type

    @property
    def rate(self):
        return self.source1.rate

    @property
    def channels(self):
        return self.source1.channels

    @property
    def layout(self):
        return self.source1.layout

    @property
    def sar(self):
        return self.source1.sar

    @property
    def height(self):
        return self.source1.height

    @property
    def width(self):
        return self.source1.width

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
        return self.source1.framecount

    @framecount.deleter
    def framecount(self):
        return

    @property
    def pts_time(self):
        return self.source1.pts_time

    @property
    def duration(self):
        return self.source1.duration

    @duration.deleter
    def duration(self):
        return

    @property
    def durations(self):
        return self.source1.durations

    @durations.deleter
    def durations(self):
        return

    @property
    def type(self):
        return self.source1.type

    @property
    def time_base(self):
        return self.source1.time_base

    def iterFrames(self, start=0, end=None, whence="pts"):
        frames1 = self.source1.iterFrames(start, end, whence)
        frames2 = self.source2.iterFrames(start, end, whence)

        if self.type == "video":
            for frame1, frame2 in zip(frames1, frames2):
                k = self.source1.frameIndexFromPts(frame1.pts)

                A = frame1.to_rgb().to_ndarray()
                B = frame2.to_rgb().to_ndarray()

                if not 1&self.flags:
                    A = (1 - (k + 1)/(self.framecount + 2))*A

                if not 2&self.flags:
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

                if not 1&self.flags:
                    A = AA[:N]*numpy.cos(T*numpy.pi/2/self.duration)**2

                else:
                    A = AA[:N]

                if not 2&self.flags:
                    B = BB[:N]*numpy.sin(T*numpy.pi/2/self.duration)**2

                else:
                    B = BB[:N]

                C = A + B

                #if self.format == "fltp":
                    #newframe = AudioFrame.from_ndarray(numpy.float32(C), format="fltp", layout=frame1.layout.name)

                #elif self.format == "s16":
                    #C = numpy.int16(2**15*C+0.5)
                    #C = C.transpose().reshape(1, C.size)
                    ##print("C", C.dtype, C.shape)
                    #newframe = AudioFrame.from_ndarray(C, format="s16", layout=frame1.layout.name)

                newframe = toAFrame(C, layout=self.layout)

                newframe.rate = frame1.rate
                newframe.pts = int(T/frame1.time_base + 0.00001)
                newframe.time_base = frame1.time_base
                yield newframe

                T += N/self.rate
                AA = AA[N:]
                BB = BB[N:]
