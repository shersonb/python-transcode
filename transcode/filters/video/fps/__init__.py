from ..base import BaseVideoFilter
from ...base import CacheResettingProperty
from fractions import Fraction as QQ
from numpy import arange
from transcode.util import cached


class Fps(BaseVideoFilter):
    """Change Frame Rate."""

    allowedtypes = ("video",)
    rate = CacheResettingProperty("rate")

    def __init__(self, rate=QQ(24000, 1001),
                 prev=None, next=None, parent=None):
        super().__init__(prev=prev, next=next, parent=parent)
        self.rate = rate

    def __getstate__(self):
        state = super().__getstate__()
        state["rate"] = self.rate
        return state

    def __setstate__(self, state):
        self.rate = state.get("rate", QQ(24000, 1001))
        super().__setstate__(state)

    def __str__(self):
        if self is None:
            return "Fps"
        return f"Fps({self.rate})"

    @cached
    def pts_time(self):
        return arange(0, self.prev.framecount/float(self.rate), 1/float(self.rate))

    @cached
    def duration(self):
        return self.framecount/float(self.rate)

    def _processFrames(self, iterable):
        for frame in iterable:
            index = self.prev.frameIndexFromPts(frame.pts)
            frame.pts = self.pts[index]
            yield frame

    @staticmethod
    def QtDlgClass():
        from .qfps import FpsDlg
        return FpsDlg


