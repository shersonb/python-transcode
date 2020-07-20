from ...util import cached, search
from ..base import BaseFilter
from ...containers.basereader import Track
from fractions import Fraction as QQ
import numpy

class BaseAudioFilter(BaseFilter):
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


