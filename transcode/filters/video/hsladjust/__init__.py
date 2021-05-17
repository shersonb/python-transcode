from ..base import BaseVideoFilter
from ...base import CacheResettingProperty
from fractions import Fraction as QQ
from numpy import arange, moveaxis, float, zeros, uint8, float64, array
from numpy import min as npmin
from transcode.util import cached
from transcode.avarrays import toNDArray, toVFrame


class HSLAdjust(BaseVideoFilter):
    """Adjust Hue/Saturation/Luminosity."""

    allowedtypes = ("video",)

    def __init__(self, dh=0, sfactor=1, lgamma=1,
                 prev=None, next=None, parent=None):
        super().__init__(prev=prev, next=next, parent=parent)
        self.dh = dh
        self.sfactor = sfactor
        self.lgamma = lgamma

    def __getstate__(self):
        state = super().__getstate__()
        state["dh"] = self.dh
        state["sfactor"] = self.sfactor
        state["lgamma"] = self.lgamma
        return state

    def __setstate__(self, state):
        self.dh = state.get("dh", 0)
        self.sfactor = state.get("sfactor", 1)
        self.lgamma = state.get("lgamma", 1)
        super().__setstate__(state)

    def __str__(self):
        if self is None:
            return "HSLAdjust"
        return f"HSLAdjust({self.dh}, {self.sfactor}, {self.lgamma})"

    def _processFrames(self, iterable):
        for frame in iterable:
            if frame.format.name != "rgb24":
                frame = frame.to_rgb()

            A = toNDArray(frame)/256
            R, G, B = moveaxis(A, 2, 0)
            V = A.max(axis=2)
            C = V - A.min(axis=2)
            L = V - C/2

            H = zeros(A.shape[:2], dtype=float64)

            case1 = C == 0
            case2 = (V == R)*(~case1)
            case3 = (V == G)*(~case1)*(~case2)
            case4 = (V == B)*(~case1)*(~case2)*(~case3)

            H[case2] = (60*(G[case2] - B[case2])/C[case2]) % 360
            H[case3] = 60*(2 + (B[case3] - R[case3])/C[case3])
            H[case4] = 60*(4 + (R[case4] - G[case4])/C[case4])

            SL = zeros(A.shape[:2], dtype=float64)

            case5 = (L > 0)*(L < 1)
            SL[case5] = (V[case5] - L[case5])/npmin((L[case5], 1-L[case5]), axis=0)

            # --- Adjustments to HSL go here ---

            H += self.dh
            H %= 360

            SL *= self.sfactor

            L = 1 - (1 - L)**self.lgamma

            C = (1 - abs(2*L - 1))*SL

            H /= 60
            X = C*(1 - abs(H % 2 - 1))

            case1 = (H <= 1)
            case2 = (1 < H)*(H <= 2)
            case3 = (2 < H)*(H <= 3)
            case4 = (3 < H)*(H <= 4)
            case5 = (4 < H)*(H <= 5)
            case6 = H > 5

            m = L - C/2

            R = zeros(R.shape, dtype=float64)
            G = zeros(G.shape, dtype=float64)
            B = zeros(B.shape, dtype=float64)

            R[case1] = C[case1]
            G[case1] = X[case1]

            R[case2] = X[case2]
            G[case2] = C[case2]

            G[case3] = C[case3]
            B[case3] = X[case3]

            G[case4] = X[case4]
            B[case4] = C[case4]

            B[case5] = C[case5]
            R[case5] = X[case5]

            B[case6] = X[case6]
            R[case6] = C[case6]

            R += m
            G += m
            B += m

            A = (256*moveaxis((R, G, B), 0, 2)).clip(min=0, max=255)
            A = uint8(A)

            newframe = toVFrame(A, frame.format.name)

            newframe.time_base = frame.time_base
            newframe.pts = frame.pts
            newframe.pict_type = frame.pict_type

            yield newframe

    @staticmethod
    def QtDlgClass():
        from .qhsladjust import QHSLAdjDlg
        return QHSLAdjDlg
