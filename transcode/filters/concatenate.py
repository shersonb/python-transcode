from .video.base import BaseVideoFilter
from .audio.base import BaseAudioFilter
from .base import BaseFilter
import numpy
from collections import OrderedDict
from itertools import count
from ..util import cached
from ..avarrays import toNDArray, toAFrame
from fractions import Fraction as QQ

class Concatenate(BaseVideoFilter, BaseAudioFilter):
    def __init__(self, segments=[], time_base=QQ(1, 10**9), **kwargs):
        self.segments = list(segments)
        self.time_base = time_base
        super().__init__(**kwargs)

    @property
    def dependencies(self):
        dependencies = set(self.segments)
        for source in self.segments:
            if isinstance(source, BaseFilter):
                dependencies.update(source.dependencies)
        return dependencies

    @cached
    def pts_time(self):
        L = []
        T = 0

        for segment in self.segments:
            L.append(segment.pts_time + T)
            T += segment.duration

        return numpy.concatenate(L)

    @cached
    def pts(self):
        return numpy.int0(self.pts_time/self.time_base + 0.0001)

    @cached
    def duration(self):
        return sum(segment.duration for segment in self.segments)

    @cached
    def durations(self):
        return numpy.int0(numpy.concatenate([segment.durations*segment.time_base/self.time_base for segment in self.segments]) + 0.0001)

    @cached
    def sizes(self):
        return numpy.concatenate([segment.sizes for segment in self.segments])

    @cached
    def framecount(self):
        return sum(segment.framecount for segment in self.segments)

    @property
    def type(self):
        if len(self.segments):
            return self.segments[0].type

    @property
    def codec(self):
        if len(self.segments):
            return self.segments[0].codec

    @property
    def extradata(self):
        if len(self.segments):
            return self.segments[0].extradata

    @property
    def format(self):
        if len(self.segments):
            return self.segments[0].format

    @property
    def bitdepth(self):
        if len(self.segments):
            return self.segments[0].bitdepth

    @property
    def defaultDuration(self):
        if len(self.segments):
            return self.segments[0].defaultDuration

    @property
    def rate(self):
        if len(self.segments):
            return self.segments[0].rate

    @property
    def layout(self):
        if len(self.segments):
            return self.segments[0].layout

    @property
    def channels(self):
        if len(self.segments):
            return self.segments[0].channels

    @property
    def width(self):
        if len(self.segments):
            return self.segments[0].width

    @property
    def height(self):
        if len(self.segments):
            return self.segments[0].height

    @property
    def sar(self):
        if len(self.segments):
            return self.segments[0].sar

    @property
    def prev(self):
        raise AttributeError

    @prev.setter
    def prev(self, value):
        return

    #def QTableColumns(self):
        #cols = []
        #for filt in self:
            #if hasattr(filt, "QTableColumns") and callable(filt.QTableColumns):
                #cols.extend(filt.QTableColumns())
        #return cols


    def iterFrames(self, start=0, end=None, whence=None):
        if self.type == "video" and whence is None:
            whence = "framenumber"

        elif self.type in ("audio", "subtitle") and whence is None:
            whence = "seconds"

        N = 0
        K = count(start)
        T = 0

        for segment in self.segments:
            if whence == "framenumber":
                if start >= N + segment.framecount:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif N <= start:
                    if end is not None and end < N + segment.framecount:
                        frames = segment.iterFrames(start - N, end - N, whence)

                    else:
                        frames = segment.iterFrames(start - N, None, whence)

                elif end is None or end >= N + segment.framecount:
                    frames = segment.iterFrames()

                elif end > N:
                    frames = segment.iterFrames(None, end - N, whence)

                else:
                    break

            elif whence == "pts":
                if start*segment.time_base >= T + segment.duration:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif T <= start*segment.time_base:
                    if end is not None and end*segment.time_base < T + segment.duration:
                        frames = segment.iterFrames(start - int(T/segment.time_base + 0.5), end - int(T/segment.time_base + 0.5), whence)

                    else:
                        frames = segment.iterFrames(start - int(T/segment.time_base + 0.5), None, whence)

                elif end is None or end*segment.time_base >= T + segment.duration:
                    frames = segment.iterFrames()

                elif end*segment.time_base > T:
                    frames = segment.iterFrames(None, end - int(T/segment.time_base + 0.5), whence)

                else:
                    break

            elif whence == "seconds":
                if start >= T + segment.duration:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif T <= start:
                    if end is not None and end < T + segment.duration:
                        frames = segment.iterFrames(start - T, end - T, whence)

                    else:
                        frames = segment.iterFrames(start - T, None, whence)

                elif end is None or end >= T + segment.duration:
                    frames = segment.iterFrames()

                elif end > T:
                    frames = segment.iterFrames(None, end - T, whence)

                else:
                    break

            for frame in frames:
                frame.pts = int((T + frame.pts*frame.time_base)/self.time_base + 0.5)
                frame.time_base = self.time_base
                yield frame

            N += segment.framecount
            T += segment.duration

    def iterPackets(self, start=0, end=None, whence="pts"):
        if self.type == "video" and whence is None:
            whence = "framenumber"

        elif self.type in ("audio", "subtitle") and whence is None:
            whence = "seconds"

        N = 0
        K = count(start)
        T = 0

        for segment in self.segments:
            if whence == "framenumber":
                if start >= N + segment.framecount:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif N <= start:
                    if end is not None and end < N + segment.framecount:
                        frames = segment.iterFrames(start - N, end - N, whence)

                    else:
                        frames = segment.iterFrames(start - N, None, whence)

                elif end is None or end >= N + segment.framecount:
                    frames = segment.iterFrames()

                elif end > N:
                    frames = segment.iterFrames(None, end - N, whence)

                else:
                    break

            elif whence == "pts":
                if start*segment.time_base >= T + segment.duration:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif T <= start*segment.time_base:
                    if end is not None and end*segment.time_base < T + segment.duration:
                        frames = segment.iterFrames(start - int(T/segment.time_base + 0.5), end - int(T/segment.time_base + 0.5), whence)

                    else:
                        frames = segment.iterFrames(start - int(T/segment.time_base + 0.5), None, whence)

                elif end is None or end*segment.time_base >= T + segment.duration:
                    frames = segment.iterFrames()

                elif end*segment.time_base > T:
                    frames = segment.iterFrames(None, end - int(T/segment.time_base + 0.5), whence)

                else:
                    break

            elif whence == "seconds":
                if start >= T + segment.duration:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif T <= start:
                    if end is not None and end < T + segment.duration:
                        frames = segment.iterFrames(start - T, end - T, whence)

                    else:
                        frames = segment.iterFrames(start - T, None, whence)

                elif end is None or end >= T + segment.duration:
                    frames = segment.iterFrames()

                elif end > T:
                    frames = segment.iterFrames(None, end - T, whence)

                else:
                    break

            for frame in frames:
                frame.pts = int((T + frame.pts*frame.time_base)/self.time_base + 0.5)
                frame.time_base = self.time_base
                yield frame

            N += segment.framecount
            T += segment.duration

        if self.type == "video" and whence is None:
            whence = "framenumber"

        elif self.type in ("audio", "subtitle") and whence is None:
            whence = "seconds"

        N = 0
        K = count(start)
        T = 0

        for segment in self.segments:
            if whence == "framenumber":
                if start >= N + segment.framecount:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif N <= start:
                    if end is not None and end < N + segment.framecount:
                        frames = segment.iterFrames(start - N, end - N, whence)

                    else:
                        frames = segment.iterFrames(start - N, None, whence)

                elif end is None or end >= N + segment.framecount:
                    frames = segment.iterFrames()

                elif end > N:
                    frames = segment.iterFrames(None, end - N, whence)

                else:
                    break

            elif whence == "pts":
                if start*segment.time_base >= T + segment.duration:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif T <= start*segment.time_base:
                    if end is not None and end*segment.time_base < T + segment.duration:
                        frames = segment.iterFrames(start - int(T/segment.time_base + 0.5), end - int(T/segment.time_base + 0.5), whence)

                    else:
                        frames = segment.iterFrames(start - int(T/segment.time_base + 0.5), None, whence)

                elif end is None or end*segment.time_base >= T + segment.duration:
                    frames = segment.iterFrames()

                elif end*segment.time_base > T:
                    frames = segment.iterFrames(None, end - int(T/segment.time_base + 0.5), whence)

                else:
                    break

            elif whence == "seconds":
                if start >= T + segment.duration:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif T <= start:
                    if end is not None and end < T + segment.duration:
                        frames = segment.iterFrames(start - T, end - T, whence)

                    else:
                        frames = segment.iterFrames(start - T, None, whence)

                elif end is None or end >= T + segment.duration:
                    frames = segment.iterFrames()

                elif end > T:
                    frames = segment.iterFrames(None, end - T, whence)

                else:
                    break

            for frame in frames:
                frame.pts = int((T + frame.pts*frame.time_base)/self.time_base + 0.5)
                frame.time_base = self.time_base
                yield frame

            N += segment.framecount
            T += segment.duration


    def append(self, segment):
        self.segments.append(segment)

    def extend(self, segments):
        self.segments.extend(segments)

    def __reduce__(self):
        return type(self), (), self.__getstate__(), iter(self.segments)

    def __getstate__(self):
        state = OrderedDict()

        if self.time_base:
            state["time_base"] = self.time_base

        return state

    def __setstate__(self, state):
        self.time_base = state.get("time_base", QQ(1, 10**9))
