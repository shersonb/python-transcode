#!/usr/bin/python
import numpy
from .base import BaseVideoFilter
from ...avarrays import toNDArray, toVFrame
from av.video import VideoFrame

class HFlip(BaseVideoFilter):
    """Horizontal Flip."""

    def __str__(self):
        return "Horizontal Flip"

    def _processFrames(self, iterable):
        for frame in iterable:
            if frame.format.name == "rgb24":
                A = toNDArray(frame)
                newframe = toVFrame(A[:, ::-1], frame.format.name)

            elif frame.format.name == "yuv420p":
                Y, U, V = toNDArray(frame)
                newframe = toVFrame((Y[:, ::-1], U[:, ::-1], V[:, ::-1]), frame.format.name)

            newframe.pts = frame.pts
            newframe.time_base = frame.time_base
            newframe.pict_type = frame.pict_type
            yield newframe

class VFlip(BaseVideoFilter):
    """Vertical Flip."""

    def __str__(self):
        return "Vertical Flip"

    def _processFrames(self, iterable):
        for frame in iterable:
            if frame.format.name == "rgb24":
                A = toNDArray(frame)
                newframe = toVFrame(A[::-1], frame.format.name)

            elif frame.format.name == "yuv420p":
                Y, U, V = toNDArray(frame)
                newframe = toVFrame((Y[::-1], U[::-1], V[::-1]), frame.format.name)

            newframe.pts = frame.pts
            newframe.time_base = frame.time_base
            newframe.pict_type = frame.pict_type
            yield newframe

