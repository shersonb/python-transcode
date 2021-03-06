#!/usr/bin/python
from ..base import BaseVideoFilter
from transcode.util import cached
import numpy


class KeyFrames(BaseVideoFilter, set):
    def __init__(self, keyframes=[], prev=None, next=None):
        set.__init__(self, keyframes)
        BaseVideoFilter.__init__(self, prev=prev, next=next)

    def reset_cache(self, start=0, end=None):
        del self.new_keyframes
        super().reset_cache(start, end)

    @property
    def time_base(self):
        if self.prev is not None:
            return self.prev.time_base

    @time_base.setter
    def time_base(self, value):
        self.reset_cache()

    def copy(self):
        return type(self)(self)

    def __str__(self):
        if self is None:
            return "Key Frames"
        if len(self) == 1:
            return "Key Frames (1 key frame)"
        return "Key Frames (%d key frames)" % len(self)

    def getinitargs(self):
        return sorted(self)

    @cached
    def new_keyframes(self):
        if len(self) == 0:
            return set()

        n = numpy.int0(sorted(self))
        m = self.prev.cumulativeIndexMap[n]

        while (m < 0).any():
            n[m < 0] += 1
            m = self.prev.cumulativeIndexMap[n]

        return set(m)

    def _processFrames(self, iterable):
        frame = iterable.send(None)
        firstpts = frame.pts
        n = self.prev.frameIndexFromPts(firstpts)

        if n in self.new_keyframes:
            frame.pict_type = "I"

        yield frame

        for k, frame in enumerate(iterable, n + 1):
            if k in self.new_keyframes:
                frame.pict_type = "I"

            yield frame

    def add(self, item):
        set.add(self, int(item))

    def __getstate__(self):
        state = super().__getstate__()
        state["keyframes"] = list(self)
        return state

    def __setstate__(self, state):
        self.clear()
        self.update(state.get("keyframes", []))
        super().__setstate__(state)

    def __hash__(self):
        return BaseVideoFilter.__hash__(self)

    def QtTableColumns(self):
        from .qkeyframes import KeyFrameCol
        return [KeyFrameCol(self)]
