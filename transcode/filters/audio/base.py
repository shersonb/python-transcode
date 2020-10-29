from ...util import cached
from ..base import BaseFilter


class BaseAudioFilter(BaseFilter):
    allowedtypes = ("audio",)

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
    def bitdepth(self):
        if self.prev:
            return self.prev.bitdepth

    @property
    def prev(self):
        return self._prev or self._source

    @prev.setter
    def prev(self, value):
        if value is not None and value.type != "audio":
            raise ValueError(
                f"Invalid media source for Audio filter: {value.type}")

        self._prev = value
        self.reset_cache()

    @cached
    def duration(self):
        return self.prev.duration
