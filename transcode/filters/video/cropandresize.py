from . import zoned
from .base import BaseVideoFilter
from ...util import cached, numpify
from itertools import count
import numpy
from av.video import VideoFrame
from PIL import Image
from collections import OrderedDict
import sys
from fractions import Fraction as QQ
import regex

class Crop(BaseVideoFilter):
    def __init__(self, croptop=0, cropbottom=0, cropleft=0, cropright=0,
                 prev=None, next=None, parent=None):
        self.croptop = croptop
        self.cropbottom = cropbottom
        self.cropleft = cropleft
        self.cropright = cropright
        super().__init__(prev=prev, next=next, parent=parent)

    def __getstate__(self):
        state = super().__getstate__()
        state["croptop"] = self.croptop
        state["cropbottom"] = self.cropbottom
        state["cropleft"] = self.cropleft
        state["cropright"] = self.cropright
        return state

    def __setstate__(self, state):
        self.croptop = state.get("croptop", 0)
        self.cropbottom = state.get("cropbottom", 0)
        self.cropleft = state.get("cropleft", 0)
        self.cropright = state.get("cropright", 0)
        super().__setstate__(state)

    def __str__(self):
        if self is None:
            return "Crop"
        return "Crop(%d, %d, %d, %d)" % (self.croptop, self.cropbottom, self.cropleft, self.cropright)

    @property
    def width(self):
        if self.prev is not None:
            return self.prev.width - self.cropleft - self.cropright

    @property
    def height(self):
        if self.prev is not None:
            return self.prev.height - self.croptop - self.cropbottom

    def _processFrames(self, iterable):
        for frame in iterable:
            if frame.format.name == "rgb24":
                A = frame.to_ndarray()
                A = A[
                    self.croptop:-self.cropbottom if self.cropbottom else None,
                    self.cropleft:-self.cropright if self.cropright else None
                    ].copy(order="C")

                newframe = VideoFrame.from_ndarray(A)

            elif frame.format.name == "yuv420p":
                H = frame.height
                W = frame.width
                A = frame.to_ndarray()
                Y = A[:H]
                U = A[H:H*5//4].reshape(H//2, W//2)
                V = A[H*5//4:].reshape(H//2, W//2)

                Y = Y[
                    self.croptop:-self.cropbottom if self.cropbottom else None,
                    self.cropleft:-self.cropright if self.cropright else None
                    ]

                U = U[
                    self.croptop//2 if self.croptop else None:-self.cropbottom//2 if self.cropbottom else None,
                    self.cropleft//2 if self.cropleft else None:-self.cropright//2 if self.cropright else None
                    ]

                V = V[
                    self.croptop//2 if self.croptop else None:-self.cropbottom//2 if self.cropbottom else None,
                    self.cropleft//2 if self.cropleft else None:-self.cropright//2 if self.cropright else None
                    ]

                newH, newW = Y.shape
                U = U.reshape(newH//4, newW)
                V = V.reshape(newH//4, newW)

                A = numpy.concatenate((Y, U, V), axis=0).copy(order="C")

                newframe = VideoFrame.from_ndarray(A, format="yuv420p")

            newframe.time_base = frame.time_base
            newframe.pts = frame.pts
            newframe.pict_type = frame.pict_type

            yield newframe

    #@classmethod
    #def qinitialize(cls, prev, parent):
        #from movie.qcropandresize import CropDlg
        #dlg = CropDlg(0, 0, 0, 0, prev, parent)
        #if dlg.exec_():
            #cnr = cls(dlg.cropTop.value(), dlg.cropBottom.value(), dlg.cropLeft.value(), dlg.cropRight.value())
            #return cnr

    #def qconfig(self, parent):
        #from movie.qcropandresize import CropDlg
        #dlg = CropDlg(self.croptop, self.cropbottom, self.cropleft, self.cropright, self.prev, parent)
        #if dlg.exec_():
            #self.croptop = dlg.cropTop.value()
            #self.cropbottom = dlg.cropBottom.value()
            #self.cropleft = dlg.cropLeft.value()
            #self.cropright = dlg.cropRight.value()
            #return True

class Resize(BaseVideoFilter):
    getinitkwargs = ["width", "height", "sar", "resample", "box"]

    def __init__(self, width=None, height=None, sar=1, resample=Image.LANCZOS, box=None,
                 prev=None, next=None, parent=None):
        self.width = width
        self.height = height
        self.resample = resample
        self.box = box
        self.sar = sar
        super().__init__(prev=prev, next=next, parent=parent)

    def __getstate__(self):
        state = super().__getstate__()
        state["width"] = self.width
        state["height"] = self.height
        state["resample"] = self.resample
        state["box"] = self.box
        state["sar"] = self.sar
        return state

    def __setstate__(self, state):
        self.width = state.get("width")
        self.height = state.get("height")
        self.resample = state.get("resample")
        self.box = state.get("box")
        self.sar = state.get("sar", 1)
        super().__setstate__(state)

    def __str__(self):
        if self is None:
            return "Resize"
        return "Resize(width=%d, height=%d, sar=%s)" % (self.width, self.height, self.sar)

    def __repr__(self):
        if self is None:
            return "Resize"
        return "Resize(width=%d, height=%d, sar=%s)" % (self.width, self.height, self.sar)

    @property
    def sar(self):
        return self._sar

    @sar.setter
    def sar(self, value):
        self._sar = value

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._width = value

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self._height = value

    def _processFrames(self, iterable):
        for frame in iterable:
            im = frame.to_image()
            im = im.resize((self.width, self.height), self.resample, self.box)
            newframe = VideoFrame.from_image(im)
            newframe.time_base = frame.time_base
            newframe.pts = frame.pts
            newframe.pict_type = frame.pict_type
            yield newframe

    #@classmethod
    #def qinitialize(cls, prev, parent):
        #from movie.qcropandresize import ResizeDlg
        #dlg = ResizeDlg(parent)
        #dlg.setWindowTitle("Configure Resize")
        #if prev is not None:
            #if prev.width is not None:
                #dlg.width.setValue(prev.width)
            #if prev.height is not None:
                #dlg.height.setValue(prev.height)
            #if prev.sar is not None:
                #dlg.sar.setText(str(prev.sar))
        #val = dlg.exec_()

        #if val:
            #sar = dlg.sar.text()
            #if regex.match(r"^\d+/\d+$", sar):
                #sar = QQ(sar)
            #elif regex.match(r"^\d+$", sar):
                #sar = int(sar)
            #else:
                #sar = float(sar)
            #cnr = cls(width=dlg.width.value(), height=dlg.height.value(), sar=sar)
            #return cnr

    #def qconfig(self, parent):
        #from movie.qcropandresize import ResizeDlg
        #dlg = ResizeDlg(parent)
        #dlg.setWindowTitle("Configure Resize")
        #dlg.width.setValue(self.width)
        #dlg.height.setValue(self.height)
        #dlg.sar.setText(str(self.sar))
        #val = dlg.exec_()

        #if val:
            #sar = dlg.sar.text()
            #if regex.match(r"^\d+/\d+$", sar):
                #self.sar = QQ(sar)
            #elif regex.match(r"^\d+$", sar):
                #self.sar = int(sar)
            #else:
                #self.sar = float(sar)
            #self.width = dlg.width.value()
            #self.height = dlg.height.value()
            #return True

class CropZone(zoned.Zone):
    def __init__(self, src_start, croptop=0, cropbottom=0, cropleft=0, cropright=0, rowanalysis=None, colanalysis=None,
                 **kwargs):
        super().__init__(src_start=src_start, **kwargs)
        self.croptop = croptop
        self.cropbottom = cropbottom
        self.cropleft = cropleft
        self.cropright = cropright
        self.rowanalysis = rowanalysis
        self.colanalysis = colanalysis

    def __getstate__(self):
        state = OrderedDict()
        state["croptop"] = self.croptop
        state["cropbottom"] = self.cropbottom
        state["cropleft"] = self.cropleft
        state["cropright"] = self.cropright

        if self.rowanalysis is not None:
            state["rowanalysis"] = self.rowanalysis

        if self.rowanalysis is not None:
            state["colanalysis"] = self.colanalysis

        return state

    def __setstate__(self, state):
        self.croptop = state.get("croptop", 0)
        self.cropbottom = state.get("cropbottom", 0)
        self.cropleft = state.get("cropleft", 0)
        self.cropright = state.get("cropright", 0)
        self.rowanalysis = state.get("rowanalysis")
        self.colanalysis = state.get("colanalysis")

    def analyzeFrames(self, iterable=None):
        if iterable is None:
            iterable = self.parent.prev.readFrames(self.prev_start, self.prev_end)

        R = []
        C = []

        for frame in iterable:
            A = frame.to_ndarray()

            if frame.format.name == "rgb24":
                print(A.shape)
                R.append(A.max(axis=(0, 2)))
                C.append(A.max(axis=(1, 2)))

            else:
                h, w = A.shape
                A = A[:2*h//3]
                R.append(A.max(axis=0))
                C.append(A.max(axis=1))

        self.rowanalysis = numpy.array(R).max(axis=0)
        self.colanalysis = numpy.array(C).max(axis=0)
        return self.rowanalysis, self.colanalysis

    def autocrop(self, setvalues=True):
        if self.rowanalysis is None or self.colanalysis is None:
            self.analyzeFrames()

        S = self.rowanalysis < 32
        D = self.colanalysis < 32

        for j in range(len(self.rowanalysis)):
            if not S[j].all():
                cropleft = (j - 1) + (1 - j) % 2
                break
        else:
            cropleft = None

        for j in range(len(self.rowanalysis) - 1, 0, -1):
            if not S[j].all():
                cropright = len(self.rowanalysis) - (j + 1) + (j + 1)%2
                break
        else:
            cropright = None

        for j in range(len(self.colanalysis)):
            if not D[j].all():
                croptop = (j - 1) + (1 - j) % 2
                break
        else:
            croptop = None

        for j in range(len(self.colanalysis) - 1, 0, -1):
            if not D[j].all():
                cropbottom = len(self.colanalysis) - (j + 1) + (j + 1)%2
                break
        else:
            cropbottom = None

        if setvalues:
            self.croptop = croptop
            self.cropbottom = cropbottom
            self.cropleft = cropleft
            self.cropright = cropright
        #print(self, (croptop, cropbottom, cropleft, cropright))

    def processFrames(self, iterable, prev_start):
        for frame in iterable:
            if frame.format.name == "rgb24":
                A = frame.to_ndarray()

                B = A[
                    self.croptop:-self.cropbottom if self.cropbottom else None,
                    self.cropleft:-self.cropright if self.cropright else None
                    ].copy(order="C")

                newframe = VideoFrame.from_ndarray(B)

            elif frame.format.name == "yuv420p":
                H = frame.height
                W = frame.width
                A = frame.to_ndarray()
                Y = A[:H]
                U = A[H:H*5//4].reshape(H//2, W//2)
                V = A[H*5//4:].reshape(H//2, W//2)

                Y = Y[
                    self.croptop:-self.cropbottom if self.cropbottom else None,
                    self.cropleft:-self.cropright if self.cropright else None
                    ]

                U = U[
                    self.croptop//2 if self.croptop else None:-self.cropbottom//2 if self.cropbottom else None,
                    self.cropleft//2 if self.cropleft else None:-self.cropright//2 if self.cropright else None
                    ]

                V = V[
                    self.croptop//2 if self.croptop else None:-self.cropbottom//2 if self.cropbottom else None,
                    self.cropleft//2 if self.cropleft else None:-self.cropright//2 if self.cropright else None
                    ]

                newH, newW = Y.shape
                U = U.reshape(newH//4, newW)
                V = V.reshape(newH//4, newW)

                A = numpy.concatenate((Y, U, V), axis=0).copy(order="C")

                newframe = VideoFrame.from_ndarray(A, format="yuv420p")

            newframe.time_base = frame.time_base
            newframe.pts = frame.pts
            newframe.pict_type = frame.pict_type

            yield newframe

class CropScenes(zoned.ZonedFilter):
    zoneclass = CropZone
    #getinitkwargs = ["zones", "width", "height", "sar", "resample", "box"]

    def __init__(self, zones=[], width=None, height=None, resample=Image.LANCZOS,
                 box=None, sar=1, **kwargs):
        self.width = width
        self.sar = sar
        self.height = height
        self.resample = resample
        self.box = box
        super().__init__(zones=zones, **kwargs)

    def __getstate__(self):
        state = super().__getstate__()
        state["width"] = self.width
        state["height"] = self.height
        state["resample"] = self.resample
        state["box"] = self.box
        state["sar"] = self.sar
        return state

    def __setstate__(self, state):
        self.width = state.get("width")
        self.height = state.get("height")
        self.resample = state.get("resample")
        self.box = state.get("box")
        self.sar = state.get("sar", 1)
        super().__setstate__(state)

    def __repr__(self):
        if self is None:
            return "Crop/Resize Scenes"

        if len(self) == 1:
            return "Crop/Resize Scenes (1 zone, width=%d, height=%d, sar=%s)" % (self.width, self.height, self.sar)

        return "Crop/Resize Scenes (%d zones, width=%d, height=%d, sar=%s)" % (len(self), self.width, self.height, self.sar)

    def __str__(self):
        if self is None:
            return "Crop/Resize Scenes"

        if len(self) == 1:
            return "Crop/Resize Scenes (1 zone, width=%d, height=%d, sar=%s)" % (self.width, self.height, self.sar)

        return "Crop/Resize Scenes (%d zones, width=%d, height=%d, sar=%s)" % (len(self), self.width, self.height, self.sar)

    #@classmethod
    #def qinitialize(cls, prev, parent):
        #from movie.qcropandresize import ResizeDlg
        #dlg = ResizeDlg(parent)
        #dlg.setWindowTitle("Configure Resize")
        #if prev is not None:
            #if prev.width is not None:
                #dlg.width.setValue(prev.width)
            #if prev.height is not None:
                #dlg.height.setValue(prev.height)
            #if prev.sar is not None:
                #dlg.sar.setText(str(prev.sar))
        #val = dlg.exec_()

        #if val:
            #sar = dlg.sar.text()
            #if regex.match(r"^\d+/\d+$", sar):
                #sar = QQ(sar)
            #elif regex.match(r"^\d+$", sar):
                #sar = int(sar)
            #else:
                #sar = float(sar)
            #cnr = cls([], width=dlg.width.value(), height=dlg.height.value(), sar=sar)
            #return cnr

    #def qconfig(self, parent):
        #from movie.qcropandresize import ResizeDlg
        #dlg = ResizeDlg(parent)
        #dlg.setWindowTitle("Configure Resize")
        #dlg.width.setValue(self.width)
        #dlg.height.setValue(self.height)
        #dlg.sar.setText(str(self.sar))
        #val = dlg.exec_()

        #if val:
            #sar = dlg.sar.text()
            #if regex.match(r"^\d+/\d+$", sar):
                #self.sar = QQ(sar)
            #elif regex.match(r"^\d+$", sar):
                #self.sar = int(sar)
            #else:
                #self.sar = float(sar)
            #self.width = dlg.width.value()
            #self.height = dlg.height.value()
            #return True

    @property
    def sar(self):
        return self._sar

    @sar.setter
    def sar(self, value):
        self._sar = value

    @property
    def width(self):
        return self._width

    @width.setter
    def width(self, value):
        self._width = value

    @property
    def height(self):
        return self._height

    @height.setter
    def height(self, value):
        self._height = value

    def analyzeFrames(self):
        frames = self.prev.readFrames()

        zone = self.start_zone

        while zone is not None:
            if zone.prev_framecount is not None:
                zone_iterable = islice(frames, int(zone.prev_framecount))

            else:
                zone_iterable = frames

            A = zone.analyzeFrames(zone_iterable)
            print("% 6d-% 6d: %s" % (zone.src_start, zone.src_end, A))

            zone = zone.next_zone

    def _processFrames(self, iterable):
        for frame in super()._processFrames(iterable):
            im = frame.to_image()
            im = im.resize((self.width, self.height), self.resample, self.box)
            newframe = VideoFrame.from_image(im)
            newframe.time_base = frame.time_base
            newframe.pts = frame.pts
            newframe.pict_type = frame.pict_type
            yield newframe

    #@cached
    #def QTableColumns(self):
        #from movie.qcropandresize import CropResizeCol
        #return [CropResizeCol(self)]

