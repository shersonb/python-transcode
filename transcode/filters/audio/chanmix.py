#!/usr/bin/python
from .base import BaseAudioFilter
from ...avarrays import toNDArray, toAFrame, aconvert
import numpy


class ChannelMix(BaseAudioFilter):
    __name__ = "Channel Mixer"

    def __init__(self, matrix=None, layout=None, prev=None, next=None, parent=None):
        self.matrix = numpy.array(matrix)
        self.layout = layout
        super().__init__(prev=prev, next=next)

    def iterFrames(self, start=0, end=None, whence="pts"):
        if self.matrix is not None:
            M = numpy.matrix(self.matrix, dtype=numpy.float32)

        else:
            M = None

        for frame in self.prev.iterFrames(start, end, whence):
            frame = aconvert(frame, "fltp")

            if M is not None:
                A = toNDArray(frame)

                if self._layout is None and len(frame.layout.channels) == self.channels:
                    newframe = toAFrame(
                        (M*A.transpose()).transpose(), layout=frame.layout.name)

                else:
                    newframe = toAFrame(
                        (M*A.transpose()).transpose(), layout=self.layout)

                newframe.rate = frame.rate
                newframe.pts = frame.pts
                newframe.time_base = frame.time_base
                yield newframe

            else:
                yield frame

    @property
    def format(self):
        return "fltp"

    @property
    def channels(self):
        return len(self.matrix)

    @property
    def layout(self):
        if self._layout is None and self.prev.channels == self.channels:
            return self.prev.layout

        return self._layout

    @layout.setter
    def layout(self, value):
        self._layout = value

    def __getstate__(self):
        state = super().__getstate__()

        if self.matrix is not None:
            state["matrix"] = self.matrix

        if self._layout is not None:
            state["layout"] = self._layout

        return state

    def __setstate__(self, state):
        if state.get("matrix") is not None:
            self.matrix = numpy.array(state.get("matrix"))

        self._layout = state.get("layout")
        super().__setstate__(state)
