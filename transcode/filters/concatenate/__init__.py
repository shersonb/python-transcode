from ..video.base import BaseVideoFilter
from ..audio.base import BaseAudioFilter
from ..base import BaseFilter
import numpy
from itertools import count
from more_itertools import windowed
from ...util import cached, SourceError, IncompatibleSource, BrokenReference
from fractions import Fraction as QQ
from copy import deepcopy
import weakref
import regex


def tryweakref(obj):
    try:
        return weakref.ref(obj)

    except Exception:
        obj


class Concatenate(BaseVideoFilter, BaseAudioFilter):
    __name__ = "Concatenate"
    allowedtypes = ("audio", "video")
    sourceCount = "+"

    def __init__(self, segments=[], time_base=QQ(1, 10**9), **kwargs):
        self.segments = list(map(tryweakref, segments))
        self.time_base = time_base
        super().__init__(**kwargs)

    def __iter__(self):
        for item in self.segments:
            if isinstance(item, weakref.ref):
                yield item()

            else:
                yield item

    @property
    def dependencies(self):
        dependencies = set(self)

        for source in self:
            if isinstance(source, BaseFilter):
                dependencies.update(source.dependencies)

        return dependencies

    @cached
    def pts_time(self):
        L = []
        T = 0

        for segment in self:
            L.append(segment.pts_time + T)
            T += segment.duration

        if len(L):
            return numpy.concatenate(L)

        return numpy.array((), dtype=numpy.float64)

    @cached
    def pts(self):
        return numpy.int0(self.pts_time/float(self.time_base) + 0.0001)

    @cached
    def duration(self):
        return sum(segment.duration for segment in self)

    @cached
    def durations(self):
        if len(self):
            return numpy.int0(numpy.concatenate([
                segment.durations*segment.time_base/self.time_base
                for segment in self]) + 0.0001)

        return numpy.array((), dtype=numpy.float64)

    @cached
    def sizes(self):
        if len(self):
            return numpy.concatenate([segment.sizes for segment in self])

        return numpy.array((), dtype=numpy.int0)

    @cached
    def framecount(self):
        return sum(segment.framecount for segment in self)

    @property
    def type(self):
        if len(self):
            return self[0].type

    @property
    def codec(self):
        if len(self):
            return self[0].codec

    @property
    def extradata(self):
        if len(self):
            return self[0].extradata

    @property
    def format(self):
        if len(self):
            return self[0].format

    @property
    def bitdepth(self):
        if len(self):
            return self[0].bitdepth

    @property
    def defaultDuration(self):
        if len(self):
            return self[0].defaultDuration

    @property
    def rate(self):
        if len(self):
            return self[0].rate

    @property
    def layout(self):
        if len(self):
            return self[0].layout

    @property
    def channels(self):
        if len(self):
            return self[0].channels

    @property
    def width(self):
        if len(self):
            return self[0].width

    @property
    def height(self):
        if len(self):
            return self[0].height

    @property
    def sar(self):
        if len(self):
            return self[0].sar

    @property
    def prev(self):
        raise AttributeError

    @prev.setter
    def prev(self, value):
        return

    @property
    def cumulativeIndexMap(self):
        return numpy.arange(self.framecount)

    def iterFrames(self, start=0, end=None, whence=None):
        if self.type == "video" and whence is None:
            whence = "framenumber"

        elif self.type in ("audio", "subtitle") and whence is None:
            whence = "seconds"

        N = 0
        T = 0

        for segment in self:
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
                    frames = segment.iterFrames(0, end - N, whence)

                else:
                    break

            elif whence == "pts":
                if start*segment.time_base >= T + segment.duration:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif T <= start*segment.time_base:
                    if (end is not None
                            and end*segment.time_base < T + segment.duration):
                        frames = segment.iterFrames(
                            start - int(T/segment.time_base + 0.5),
                            end - int(T/segment.time_base + 0.5), whence)

                    else:
                        frames = segment.iterFrames(
                            start - int(T/segment.time_base + 0.5),
                            None, whence)

                elif (end is None
                      or end*segment.time_base >= T + segment.duration):
                    frames = segment.iterFrames()

                elif end*segment.time_base > T:
                    frames = segment.iterFrames(
                        0, end - int(T/segment.time_base + 0.5), whence)

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
                    frames = segment.iterFrames(0, end - T, whence)

                else:
                    break

            for frame in frames:
                frame.pts = int(
                    (T + frame.pts*frame.time_base)/self.time_base + 0.5)
                frame.time_base = self.time_base
                yield frame

            N += segment.framecount
            T += segment.duration

    def iterPackets(self, start=0, end=None, whence="pts"):
        if self.type == "video" and whence is None:
            whence = "packetnumber"

        elif self.type in ("audio", "subtitle") and whence is None:
            whence = "seconds"

        N = 0
        T = 0

        if whence == "pts":
            K = count(self.frameIndexFromPts(start, "+"))

        elif whence == "seconds":
            K = count(self.frameIndexFromPtsTime(start, "+"))

        else:
            K = count(start)

        for segment in self:
            if whence == "packetnumber":
                if start >= N + segment.framecount:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif N <= start:
                    if end is not None and end < N + segment.framecount:
                        packets = segment.iterPackets(
                            start - N, end - N, whence)

                    else:
                        packets = segment.iterPackets(start - N, None, whence)

                elif end is None or end >= N + segment.framecount:
                    packets = segment.iterPackets()

                elif end > N:
                    packets = segment.iterPackets(None, end - N, whence)

                else:
                    break

            elif whence == "pts":
                if start*segment.time_base >= T + segment.duration:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif T <= start*segment.time_base:
                    if (end is not None
                            and end*segment.time_base < T + segment.duration):
                        packets = segment.iterPackets(
                            start - int(T/segment.time_base + 0.5),
                            end - int(T/segment.time_base + 0.5), whence)

                    else:
                        packets = segment.iterPackets(
                            start - int(T/segment.time_base + 0.5),
                            None, whence)

                elif (end is None
                      or end*segment.time_base >= T + segment.duration):
                    packets = segment.iterPackets()

                elif end*segment.time_base > T:
                    packets = segment.iterPackets(
                        None, end - int(T/segment.time_base + 0.5), whence)

                else:
                    break

            elif whence == "seconds":
                if start >= T + segment.duration:
                    N += segment.framecount
                    T += segment.duration
                    continue

                elif T <= start:
                    if end is not None and end < T + segment.duration:
                        packets = segment.iterPackets(
                            start - T, end - T, whence)

                    else:
                        packets = segment.iterPackets(start - T, None, whence)

                elif end is None or end >= T + segment.duration:
                    packets = segment.iterPackets()

                elif end > T:
                    packets = segment.iterPackets(None, end - T, whence)

                else:
                    break

            for packet in packets:
                packet.pts = int(
                    (T + packet.pts*packet.time_base)/self.time_base + 0.5)

                if packet.duration:
                    packet.duration = int(
                        packet.duration*packet.time_base/self.time_base + 0.5)

                packet.time_base = self.time_base

                if self[0].source.codec == "ass":
                    match, = regex.findall(b"\\d,(.+)", packet.data)
                    packet.data = str(next(K)).encode("utf8") + b"," + match

                yield packet

            N += segment.framecount
            T += segment.duration

    def append(self, segment):
        self.segments.append(tryweakref(segment))

        if isinstance(segment, BaseFilter):
            segment.addMonitor(self)

    def insert(self, index, segment):
        self.segments.insert(index, tryweakref(segment))

        if isinstance(segment, BaseFilter):
            segment.addMonitor(self)

    def extend(self, segments):
        k = len(self)
        self.segments.extend(map(tryweakref, segments))

        for segment in self.segments[k:]:
            if isinstance(segment, weakref.ref):
                segment = segment()

            if isinstance(segment, BaseFilter):
                segment.addMonitor(self)

    def clear(self):
        for segment in self:
            if isinstance(segment, BaseFilter):
                segment.removeMonitor(self)

        self.segments.clear()

    def __getitem__(self, index):
        item = self.segments[index]

        if isinstance(index, int) and isinstance(item, weakref.ref):
            item = item()

        elif isinstance(index, slice):
            item = [x() if isinstance(x, weakref.ref) else x for x in item]

        return item

    def __len__(self):
        return len(self.segments)

    def __delitem__(self, index):
        segment = self.segments.pop(index)

        if isinstance(segment, weakref.ref):
            segment = segment()

        if isinstance(segment, BaseFilter) and segment not in self.segments:
            segment.removeMonitor(self)

    def __setitem__(self, index, value):
        oldvalue = self[index]
        self.segments[index] = tryweakref(value)

        if isinstance(value, BaseFilter):
            value.addMonitor(self)

        if isinstance(oldvalue, BaseFilter) and oldvalue not in self.segments:
            oldvalue.removeMonitor(self)

    def __reduce__(self):
        return type(self), (), self.__getstate__(), iter(self)

    def __getstate__(self):
        state = super().__getstate__()

        if self.time_base:
            state["time_base"] = self.time_base

        return state

    def __setstate__(self, state):
        self.time_base = state.get("time_base", QQ(1, 10**9))
        super().__setstate__(state)

    def __deepcopy__(self, memo):
        cls, args, state, segments = self.__reduce__()
        new = cls()
        new.__setstate__(deepcopy(state, memo))
        new.extend(segments)
        return new

    @property
    def source(self):
        raise AttributeError

    @cached
    def keyframes(self):
        kf = set()
        n = 0

        for segment in self:
            kf.update(k + n for k in segment.keyframes)
            n += segment.framecount

        return kf

    @staticmethod
    def QtDlgClass():
        from .qconcatenate import QConcatenate
        return QConcatenate

    def validate(self):
        if len(self) == 0:
            return [SourceError("No sources provided.", self)]

        exceptions = []

        for k, s in enumerate(self):
            if s is None:
                exceptions.append(BrokenReference(
                    f"Broken reference at position {k}.", self))

        for ((j, source1), (k, source2)) in windowed(filter(
                lambda X: X[1] is not None and X[1].prev is not None,
                enumerate(self)), 2):
            if source1.type != source2.type:
                exceptions.append(IncompatibleSource(
                    f"Incompatible sources: '{source1.type}' and "
                    f"'{source2.type}'.", self))

            elif source1.type == "video":
                if ((source1.width, source1.height)
                        != (source2.width, source2.height)):
                    exceptions.append(IncompatibleSource(
                        f"Sources have different resolutions: "
                        f"'{source1.width}×{source1.height}' ({j}) and "
                        f"'{source2.width}×{source2.height}' ({k}).", self))

                if source1.sar != source2.sar:
                    exceptions.append(IncompatibleSource(
                        f"Sources have different sample aspect ratios: "
                        f"'{source1.sar}' ({j}) and '{source2.sar}' ({k}).",
                        self))

            elif source1.type == "audio":
                if source1.rate != source2.rate:
                    exceptions.append(IncompatibleSource(
                        f"Sources have different sampling frequencies: "
                        f"'{source1.rate}' ({j}) and '{source2.rate}' ({k}).",
                        self))

                if source1.layout != source2.layout:
                    exceptions.append(IncompatibleSource(
                        f"Sources have different layouts: '{source1.layout}' "
                        f"({j}) and '{source2.layout}' ({k}).", self))

        return exceptions
