#!/usr/bin/python
from .base import BaseAudioFilter
from ...avarrays import toNDArray, toAFrame, aconvert

class Gain(BaseAudioFilter):
    def __init__(self, gain, prev=None, next=None, parent=None):
        self.gain = gain
        super().__init__(prev=prev, next=next)

    def iterFrames(self, start=0, end=None, whence="pts"):
        scale = 10**(self.gain/20)
        for frame in self.prev.iterFrames(start, end, whence):
            frame = aconvert(frame, "fltp")
            A = toNDArray(frame)
            B = A.dtype.type(A*scale)
            #newframe = AudioFrame.from_ndarray(B, format=frame.format.name, layout=frame.layout.name)
            newframe = toAFrame(B, layout=frame.layout.name)
            newframe.rate = frame.rate
            newframe.pts = frame.pts
            yield newframe

    @property
    def format(self):
        return "fltp"
