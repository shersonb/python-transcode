#!/usr/bin/python
import numpy
from .base import BaseVideoFilter
from av.video import VideoFrame

class HFlip(BaseVideoFilter):
    def _processFrames(self, iterable):
        for frame in iterable:
            if frame.format.name == "rgb24":
                A = frame.to_ndarray()
                B = A[:,::-1].copy("C")

            elif frame.format.name == "yuv420p":
                A = frame.to_ndarray()
                Y = A[:frame.height]
                U = A[frame.height:frame.height*5//4].reshape(frame.height//2, frame.width//2)
                V = A[frame.height*5//4:].reshape(frame.height//2, frame.width//2)
                Y = Y[:,::-1]
                U = U[:,::-1].reshape(frame.height//4, frame.width)
                V = V[:,::-1].reshape(frame.height//4, frame.width)
                B = numpy.concatenate((Y, U, V), axis=0).copy("C")

            newframe = VideoFrame.from_ndarray(B, format=frame.format.name)
            newframe.pts = frame.pts
            newframe.time_base = frame.time_base
            newframe.pict_type = frame.pict_type
            yield newframe

class VFlip(BaseVideoFilter):
    def _processFrames(self, iterable):
        for frame in iterable:
            if frame.format.name == "rgb24":
                A = frame.to_ndarray()
                B = A[::-1].copy("C")

            elif frame.format.name == "yuv420p":
                A = frame.to_ndarray()
                Y = A[:frame.height]
                U = A[frame.height:frame.height*5//4].reshape(frame.height//2, frame.width//2)
                V = A[frame.height*5//4:].reshape(frame.height//2, frame.width//2)
                Y = Y[::-1]
                U = U[::-1].reshape(frame.height//4, frame.width)
                V = V[::-1].reshape(frame.height//4, frame.width)
                B = numpy.concatenate((Y, U, V), axis=0).copy("C")

            newframe = VideoFrame.from_ndarray(B, format=frame.format.name)
            newframe.pts = frame.pts
            newframe.time_base = frame.time_base
            newframe.pict_type = frame.pict_type
            yield newframe

