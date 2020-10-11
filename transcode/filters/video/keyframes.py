#!/usr/bin/python
from .base import BaseVideoFilter
from ...util import cached
import numpy
import fractions
import itertools
from av.video import VideoFrame
import sys

class KeyFrames(BaseVideoFilter, set):
    def __init__(self, keyframes=[], prev=None, next=None):
        set.__init__(self, keyframes)
        BaseVideoFilter.__init__(self, prev=prev, next=next)

    def reset_cache(self, start=0, end=None):
        del self.prev_keyframes
        super().reset_cache(start, end)

    @property
    def time_base(self):
        if self.prev is not None:
            return self.prev.time_base

    @time_base.setter
    def time_base(self, value):
        pass

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
    def prev_keyframes(self):
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

        if n in self.prev_keyframes:
            frame.pict_type = "I"

        yield frame

        for k, frame in enumerate(iterable, n + 1):
            if k in self.prev_keyframes:
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

    def QtTableColumns(self):
        from transcode.pyqtgui.qkeyframes import KeyFrameCol
        return [KeyFrameCol(self)]
