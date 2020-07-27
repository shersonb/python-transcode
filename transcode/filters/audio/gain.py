#!/usr/bin/python
from .base import BaseAudioFilter
from ...avarrays import toNDArray, toAFrame, aconvert

class Gain(BaseAudioFilter):
    def __init__(self, gain=0, prev=None, next=None, parent=None):
        self.gain = gain
        super().__init__(prev=prev, next=next)

    def iterFrames(self, start=0, end=None, whence="pts"):
        scale = 10**(self.gain/20)
        for frame in self.prev.iterFrames(start, end, whence):
            frame = aconvert(frame, "fltp")
            A = toNDArray(frame)
            newframe = toAFrame(A*scale, layout=frame.layout.name)
            newframe.rate = frame.rate
            newframe.pts = frame.pts
            yield newframe

    @property
    def format(self):
        return "fltp"

    def __getstate__(self):
        state = super().__getstate__()
        state["gain"] = self.gain
        return state

    def __setstate__(self, state):
        self.gain = state.get("gain", 0)
        super().__setstate__(state)
