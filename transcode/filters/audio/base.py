from ...util import cached
from ..base import BaseFilter


class BaseAudioFilter(BaseFilter):
    allowedtypes = ("audio",)

    @property
    def layout(self):
        if self.prev is not None and self.prev.type == "audio":
            return self.prev.layout

    @property
    def channels(self):
        if self.prev is not None and self.prev.type == "audio":
            return self.prev.channels

    @property
    def rate(self):
        if self.prev is not None and self.prev.type == "audio":
            return self.prev.rate

    @property
    def format(self):
        if self.prev is not None and self.prev.type == "audio":
            return self.prev.format

    @property
    def bitdepth(self):
        if self.prev is not None and self.prev.type == "audio":
            return self.prev.bitdepth

    @cached
    def duration(self):
        if self.prev is not None:
            return self.prev.duration
