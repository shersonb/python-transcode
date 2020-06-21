import transcode.util
from transcode.util import cached
import transcode.filters.base
import transcode.containers.basereader
from fractions import Fraction as QQ
import threading
import numpy

class BaseAudioFilter(transcode.filters.base.BaseFilter):
    @property
    def layout(self):
        if self.prev is not None:
            return self.prev.layout

    @property
    def channels(self):
        if self.prev is not None:
            return self.prev.channels

    @property
    def rate(self):
        if self.prev is not None:
            return self.prev.rate

    @property
    def format(self):
        if self.prev:
            return self.prev.format

    @property
    def prev(self):
        return self._prev

    @prev.setter
    def prev(self, value):
        if value is not None and value.type != "audio":
            raise ValueError(f"Invalid media source for Audio filter: {value.type}")

        self._prev = value
        self.reset_cache()

    @property
    def src(self):
        if isinstance(self.prev, transcode.containers.basereader.Track):
            return self.prev

        elif isinstance(self.prev, BaseAudioFilter):
            return self.prev.src

    @cached
    def duration(self):
        return self.prev.duration

    def _processFrames(self, iterable):
        return iterable

    def processFrames(self, iterable):
        if callable(self.notify_input):
            iterable = notifyIterate(iterable, self.notify_input)

        iterable = self._processFrames(iterable)

        if callable(self.notify_output):
            iterable = notifyIterate(iterable, self.notify_output)

        return iterable

    def iterFrames(self, start=0, end=None):
        if whence == "pts":
            start = self.frameIndexFromPts(start)

            if end is not None:
                try:
                    end = self.frameIndexFromPts(end)

                except:
                    end = None

        prev_start = self.reverseIndexMap[start]

        if end is not None and end < self.framecount:
            prev_end = self.reverseIndexMap[end]

        else:
            prev_end = None

        iterable = self.prev.iterFrames(prev_start, prev_end)

        for frame in self.processFrames(iterable):
            k = self.frameIndexFromPts(frame.pts)

            if k < start:
                continue

            if end is not None and k >= end:
                break

            yield frame

    def _processFrame(self, frame):
        return frame

