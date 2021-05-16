#!/usr/bin/python
from ..base import BaseAudioFilter
from transcode.avarrays import toNDArray, toAFrame, aconvert
import numpy
import av


# TODO: Automatic matrix selection when changing output layout.
# Validation to check matrix with source and layout.

class ChannelMix(BaseAudioFilter):
    __name__ = "Channel Mixer"

    def __init__(self, matrix=[], layout=None, prev=None, next=None, parent=None):
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
    def matrix(self):
        return self._matrix

    @matrix.setter
    def matrix(self, value):
        self._matrix = numpy.array(value)

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

        if hasattr(self, "parent") and self.source is not None:
            avlayout = av.AudioLayout(value)
            srclayout = av.AudioLayout(self.source.layout)

            if self.matrix.shape[0] > len(avlayout.channels):
                self.matrix = self.matrix[:len(avlayout.channels)]

            elif self.matrix.shape[0] < len(avlayout.channels):
                self.matrix = numpy.concatenate(
                    (self.matrix,
                     numpy.zeros((len(avlayout.channels) - self.matrix.shape[0], self.matrix.shape[1]))))

    def __getstate__(self):
        state = super().__getstate__()

        if self.matrix is not None:
            state["matrix"] = self.matrix

        if self._layout is not None:
            state["layout"] = self._layout

        return state

    def __setstate__(self, state):
        # super().__setstate__(state)

        if state.get("matrix") is not None:
            self._matrix = numpy.array(state.get("matrix"))

        self._layout = state.get("layout")
        self.name = state.get("name")
        BaseAudioFilter.source.__set__(self, state.get("source"))

    @property
    def source(self):
        return BaseAudioFilter.source.__get__(self, type(self))

    @source.setter
    def source(self, value):
        if value is not None:
            if self._layout is None:
                self._layout = value.layout
                self._matrix = numpy.identity(value.channels)

            else:
                pass

            BaseAudioFilter.source.__set__(self, value)

    @classmethod
    def QtDlgClass(self):
        from .qchanmix import ChanMixDlg
        return ChanMixDlg
