#!/usr/bin/python
from .. import zoned
import numpy
from av.video import VideoFrame
from scipy.signal import fftconvolve
from collections import OrderedDict
from itertools import islice
import transcode.parmap as parallel
import threading


def histogram(A):
    N = numpy.zeros(1024, dtype=numpy.int0)
    values, frequencies = numpy.unique(A, return_counts=True)
    N[values] = frequencies
    return N


def clip(hist, tol=0.00005):
    s = hist.sum()
    minclip = tol*s
    maxclip = (1 - tol)*s
    c = hist.cumsum()

    for nmin in range(1024):
        if c[nmin + 1] >= minclip:
            break

    for nmax in reversed(range(1024)):
        if c[nmax - 1] <= maxclip:
            break

    return (nmin, nmax)


X = Y = numpy.linspace(-3, 3, 7)
X, Y = numpy.meshgrid(X, Y)
K = numpy.exp(-(X**2 + Y**2)/2)
K /= K.sum()


def analyzeFrame(frame, convkernel=K):
    A = frame.to_rgb().to_ndarray()
    KA = fftconvolve(K.reshape(K.shape + (1,)), A, mode="valid")
    R, G, B = numpy.moveaxis(numpy.int0(
        4*KA.clip(min=0, max=255) + 0.5), -1, 0)
    Rhist, Ghist, Bhist = map(histogram, (R, G, B))
    return numpy.array((Rhist, Ghist, Bhist))


class Zone(zoned.Zone):
    def __init__(self, src_start,
                 rmin=0, rmax=255, rgamma=1,
                 gmin=0, gmax=255, ggamma=1,
                 bmin=0, bmax=255, bgamma=1,
                 gamma=1, transition=False, histogram=None,
                 prev=None, next=None, parent=None):
        super().__init__(src_start=src_start,
                         prev=prev, next=next, parent=parent)
        self.rmin = rmin
        self.gmin = gmin
        self.bmin = bmin
        self.rmax = rmax
        self.gmax = gmax
        self.bmax = bmax
        self.gamma = gamma
        self.rgamma = rgamma
        self.ggamma = ggamma
        self.bgamma = bgamma
        self.transition = transition
        self.histogram = histogram

    def __getstate__(self):
        state = OrderedDict()
        if self.transition:
            state["transition"] = self.transition

        else:
            state["rmin"] = self.rmin
            state["rmax"] = self.rmax
            state["rgamma"] = self.rgamma

            state["gmin"] = self.gmin
            state["gmax"] = self.gmax
            state["ggamma"] = self.ggamma

            state["bmin"] = self.bmin
            state["bmax"] = self.bmax
            state["bgamma"] = self.bgamma

            state["gamma"] = self.gamma

        if self.histogram is not None:
            state["histogram"] = self.histogram

        return state

    def __setstate__(self, state):
        if state.get("transition"):
            self.transition = True

        else:
            self.rmin = state.get("rmin", 0)
            self.rmax = state.get("rmax", 255)
            self.rgamma = state.get("rgamma", 1)

            self.gmin = state.get("gmin", 0)
            self.gmax = state.get("gmax", 255)
            self.ggamma = state.get("ggamma", 1)

            self.bmin = state.get("bmin", 0)
            self.bmax = state.get("bmax", 255)
            self.bgamma = state.get("bgamma", 1)

            self.gamma = state.get("gamma", 1)

        if state.get("histogram") is not None:
            self.histogram = state.get("histogram")

    def __repr__(self):
        if self.parent.framecount is None:
            return "LevelsZone"

        if self.transition:
            return (f"<LevelsZone: ({self.src_start}, {self.src_end}), ["
                    f"({self.prev.rmin:.2f}, {self.prev.rmax:.2f}, "
                    f"{self.prev.rgamma:.2f}), ({self.prev.gmin:.2f}, "
                    f"{self.prev.gmax:.2f}, {self.prev.ggamma:.2f}), "
                    f"({self.prev.bmin:.2f}, {self.prev.bmax:.2f}, "
                    f"{self.prev.bgamma:.2f}), {self.prev.gamma:.4f}] - ["
                    f"({self.next.rmin:.2f}, {self.next.rmax:.2f}, "
                    f"{self.next.rgamma:.2f}), ({self.next.gmin:.2f}, "
                    f"{self.next.gmax:.2f}, {self.next.gmax:.2f}, "
                    f"{self.next.ggamma:.2f}), ({self.next.bmin:.2f}, "
                    f"{self.next.bmax:.2f}, {self.next.bgamma:.2f}), "
                    f"{self.next.gamma:.4f}], {self.framecount} frames, "
                    f"{self.duration:.3f} seconds (Transition)>")

        else:
            return (f"<LevelsZone: ({self.src_start}, {self.src_end}), ["
                    f"({self.rmin:.2f}, {self.rmax:.2f}, {self.rgamma:.2f}), "
                    f"({self.gmin:.2f}, {self.gmax:.2f}, {self.ggamma:.2f}), "
                    f"({self.bmin:.2f}, {self.bmax:.2f}, {self.bgamma:.2f}), "
                    f"{self.gamma:.4f}], {self.framecount} frames, "
                    f"{self.duration:.3f} seconds>")

    @property
    def rmin(self):
        if self.transition:
            return numpy.linspace(
                self.prev.rmin, self.next.rmin, self.framecount + 2)[1:-1]
        return self._rmin

    @rmin.setter
    def rmin(self, value):
        self._rmin = value
        del self._R

        if self.prev is not None and self.prev.transition:
            del self.prev._R

        if self.next is not None and self.next.transition:
            del self.next._R

    @property
    def rmax(self):
        if self.transition:
            return numpy.linspace(
                self.prev.rmax, self.next.rmax, self.framecount + 2)[1:-1]
        return self._rmax

    @rmax.setter
    def rmax(self, value):
        self._rmax = value
        del self._R

        if self.prev is not None and self.prev.transition:
            del self.prev._R

        if self.next is not None and self.next.transition:
            del self.next._R

    @property
    def gmin(self):
        if self.transition:
            return numpy.linspace(
                self.prev.gmin, self.next.gmin, self.framecount + 2)[1:-1]
        return self._gmin

    @gmin.setter
    def gmin(self, value):
        self._gmin = value
        del self._G

        if self.prev is not None and self.prev.transition:
            del self.prev._G

        if self.next is not None and self.next.transition:
            del self.next._G

    @property
    def gmax(self):
        if self.transition:
            return numpy.linspace(
                self.prev.gmax, self.next.gmax, self.framecount + 2)[1:-1]
        return self._gmax

    @gmax.setter
    def gmax(self, value):
        self._gmax = value
        del self._G

        if self.prev is not None and self.prev.transition:
            del self.prev._G

        if self.next is not None and self.next.transition:
            del self.next._G

    @property
    def bmin(self):
        if self.transition:
            return numpy.linspace(
                self.prev.bmin, self.next.bmin, self.framecount + 2)[1:-1]
        return self._bmin

    @bmin.setter
    def bmin(self, value):
        self._bmin = value
        del self._B

        if self.prev is not None and self.prev.transition:
            del self.prev._B

        if self.next is not None and self.next.transition:
            del self.next._B

    @property
    def bmax(self):
        if self.transition:
            return numpy.linspace(
                self.prev.bmax, self.next.bmax, self.framecount + 2)[1:-1]
        return self._bmax

    @bmax.setter
    def bmax(self, value):
        self._bmax = value
        del self._B

        if self.prev is not None and self.prev.transition:
            del self.prev._B

        if self.next is not None and self.next.transition:
            del self.next._B

    @property
    def gamma(self):
        if self.transition:
            return numpy.linspace(
                self.prev.gamma, self.next.gamma, self.framecount + 2)[1:-1]
        return self._gamma

    @gamma.setter
    def gamma(self, value):
        self._gamma = value
        del self._R, self._G, self._B
        if self.prev is not None and self.prev.transition:
            del self.prev._R, self.prev._G, self.prev._B

        if self.next is not None and self.next.transition:
            del self.next._R, self.next._G, self.next._B

    @property
    def rgamma(self):
        if self.transition:
            return numpy.linspace(
                self.prev.rgamma, self.next.rgamma, self.framecount + 2)[1:-1]
        return self._rgamma

    @rgamma.setter
    def rgamma(self, value):
        self._rgamma = value
        del self._R, self._G, self._B
        if self.prev is not None and self.prev.transition:
            del self.prev._R, self.prev._G, self.prev._B

        if self.next is not None and self.next.transition:
            del self.next._R, self.next._G, self.next._B

    @property
    def ggamma(self):
        if self.transition:
            return numpy.linspace(
                self.prev.ggamma, self.next.ggamma, self.framecount + 2)[1:-1]
        return self._ggamma

    @ggamma.setter
    def ggamma(self, value):
        self._ggamma = value
        del self._R, self._G, self._B
        if self.prev is not None and self.prev.transition:
            del self.prev._R, self.prev._G, self.prev._B

        if self.next is not None and self.next.transition:
            del self.next._R, self.next._G, self.next._B

    @property
    def bgamma(self):
        if self.transition:
            return numpy.linspace(
                self.prev.bgamma, self.next.bgamma, self.framecount + 2)[1:-1]
        return self._bgamma

    @bgamma.setter
    def bgamma(self, value):
        self._bgamma = value
        del self._R, self._G, self._B
        if self.prev is not None and self.prev.transition:
            del self.prev._R, self.prev._G, self.prev._B

        if self.next is not None and self.next.transition:
            del self.next._R, self.next._G, self.next._B

    @property
    def transition(self):
        return self._transition

    @transition.setter
    def transition(self, value):
        self._transition = value
        del self._R, self._G, self._B

    @bgamma.setter
    def bgamma(self, value):
        self._bgamma = value
        del self._R, self._G, self._B
        if self.prev is not None and self.prev.transition:
            del self.prev._R, self.prev._G, self.prev._B

        if self.next is not None and self.next.transition:
            del self.next._R, self.next._G, self.next._B

    @property
    def _R(self):
        if self._R_ is None:
            N = numpy.arange(256, dtype=numpy.float64)
            if self.transition:
                rmin, _ = numpy.meshgrid(self.rmin, N)
                rmax, _ = numpy.meshgrid(self.rmax, N)
                gamma, N = numpy.meshgrid(self.gamma*self.rgamma, N)
            else:
                rmin = self.rmin
                rmax = self.rmax
                gamma = self.gamma*self.rgamma
            N = N.clip(min=rmin, max=rmax)
            _R_ = (N - rmin)/(rmax - rmin)
            _R_ = 1 - (1 - _R_)**gamma
            self._R_ = numpy.uint8((255*_R_).clip(max=254.75) + 0.5)
        return self._R_

    @_R.deleter
    def _R(self):
        self._R_ = None

    @property
    def _G(self):
        if self._G_ is None:
            N = numpy.arange(256, dtype=numpy.float64)
            if self.transition:
                gmin, _ = numpy.meshgrid(self.gmin, N)
                gmax, _ = numpy.meshgrid(self.gmax, N)
                gamma, N = numpy.meshgrid(self.gamma*self.ggamma, N)
            else:
                gmin = self.gmin
                gmax = self.gmax
                gamma = self.gamma*self.ggamma
            N = N.clip(min=gmin, max=gmax)
            _G_ = (N - gmin)/(gmax - gmin)
            _G_ = 1 - (1 - _G_)**gamma
            self._G_ = numpy.uint8((255*_G_).clip(max=254.75) + 0.5)
        return self._G_

    @_G.deleter
    def _G(self):
        self._G_ = None

    @property
    def _B(self):
        if self._B_ is None:
            N = numpy.arange(256, dtype=numpy.float64)
            if self.transition:
                bmin, _ = numpy.meshgrid(self.bmin, N)
                bmax, _ = numpy.meshgrid(self.bmax, N)
                gamma, N = numpy.meshgrid(self.gamma*self.bgamma, N)
            else:
                bmin = self.bmin
                bmax = self.bmax
                gamma = self.gamma*self.bgamma
            N = N.clip(min=bmin, max=bmax)
            _B_ = (N - bmin)/(bmax - bmin)
            _B_ = 1 - (1 - _B_)**gamma
            self._B_ = numpy.uint8((255*_B_).clip(max=254.75) + 0.5)
        return self._B_

    @_B.deleter
    def _B(self):
        self._B_ = None

    def _processOneFrame(self, frame):
        A, fmt, pict_type, pts, time_base = frame
        R, G, B = numpy.moveaxis(A, 2, 0)

        if self.transition:
            k = self.parent.prev.frameIndexFromPts(pts) - self.prev_start
            R = self._R[R, k]
            G = self._G[G, k]
            B = self._B[B, k]

        elif (self.rmin == self.gmin == self.bmin == 0
              and self.rmax == self.gmax == self.bmax == 255
              and self.rgamma == self.ggamma
              == self.bgamma == self.gamma == 1):
            """Nothing is actually being done to the frame."""
            return frame

        else:
            if (self.rmin != 0
                    or self.rmax != 255
                    or self.gamma != 1
                    or self.rgamma != 1):
                R = self._R[R]

            if (self.gmin != 0
                    or self.gmax != 255
                    or self.gamma != 1
                    or self.ggamma != 1):
                G = self._G[G]

            if (self.bmin != 0
                    or self.bmax != 255
                    or self.gamma != 1
                    or self.bgamma != 1):
                B = self._B[B]

        A = numpy.zeros(R.shape+(3,), dtype=numpy.uint8)
        A[:, :, 0] = R
        A[:, :, 1] = G
        A[:, :, 2] = B

        return (A, fmt, pict_type, pts, time_base)

    def processFrames(self, frames, prev_start):
        def torgb(frame):
            return (frame.to_rgb()
                    if frame.format.name != "rgb24"
                    else frame)

        def totuple(frame):
            return (
                frame.to_ndarray(), frame.format.name,
                frame.pict_type.name, frame.pts, frame.time_base)

        rgb = map(torgb, frames)
        tuples = map(totuple, rgb)

        for (A, fmt, pict_type, pts, time_base) in map(
                self._processOneFrame, tuples):
            frame = VideoFrame.from_ndarray(A, fmt)
            frame.pict_type = pict_type
            frame.pts = pts
            frame.time_base = time_base
            yield frame

    def _calc_pts_time(self, m=None):
        return self.parent.prev.pts_time(m)

    def analyzeFrames(self, iterable=None, notifyprogress=None,
                      notifyfinish=None, notifycancelled=None,
                      cancelled=None):
        if iterable is None:
            iterable = self.parent.prev.iterFrames(
                self.prev_start, self.prev_end, whence="framenumber")

        A = numpy.zeros((3, 1024), dtype=numpy.int0)
        results = parallel.map(analyzeFrame, iterable)

        for k, H in enumerate(results):
            A += numpy.int0(H)

            if callable(notifyprogress):
                notifyprogress(k)

            if isinstance(cancelled, threading.Event) and cancelled.isSet():
                results.stop()
                cancelled.clear()
                self.histogram = A

                if callable(notifycancelled):
                    notifycancelled()

                return

        self.histogram = A

        if callable(notifyfinish):
            notifyfinish()

        return numpy.array(list(map(clip, A)))*0.25


class Levels(zoned.ZonedFilter):
    zoneclass = Zone

    def __str__(self):
        if self is None:
            return "Levels (multi-zoned)"
        if len(self) == 1:
            return "Levels (1 zone)"
        return "Levels (%d zones)" % len(self)

    def analyzeFrames(self):
        frames = self.prev.readFrames()

        zone = self.start

        while zone is not None:
            if zone.prev_framecount is not None:
                zone_frames = islice(frames, int(zone.prev_framecount))
            else:
                zone_frames = frames

            A = zone.analyzeFrames(zone_frames)
            print("% 6d-% 6d: %s" %
                  (zone.src_start, zone.src_end, list(map(tuple, A))))

            zone = zone.next

    @staticmethod
    def QtDlgClass():
        from .qlevels import QLevels
        return QLevels

    def QtTableColumns(self):
        from .qlevels import LevelsCol
        return [LevelsCol(self)]
