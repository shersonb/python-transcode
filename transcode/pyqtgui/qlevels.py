from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QColor, QFont, QBrush, QPen, QStandardItemModel, QIcon, QFontMetrics, QPolygon
from PyQt5.QtCore import Qt, QRegExp, QItemSelectionModel, QObject, QPoint, QRect
from PyQt5.QtWidgets import (QApplication, QItemDelegate, QLineEdit, QMenu, QAction, QAbstractItemView, QProgressDialog, QMessageBox,
                             QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QSlider, QStyleOptionSlider, QStyle, QCheckBox,
                             QLabel, QWidget, QScrollBar, QGridLayout, QComboBox, QFrame, QSizePolicy, QDoubleSpinBox)
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtGui import QRegExpValidator
from fractions import Fraction as QQ
import regex
from functools import partial
import numpy
from numpy import sqrt, log
import threading
from PIL import Image
from av import VideoFrame

from transcode.filters.video.levels import Zone
from .qframetablecolumn import ZoneCol
from .qzones import ZoneDlg, BaseShadowZone

class ShadowZone(BaseShadowZone, Zone):
    pass

class Histogram(QLabel):
    def __init__(self, histogram=None, min=0, max=256, minclip=0, maxclip=255, color=(0, 0, 0), *args, **kwargs):
        super(Histogram, self).__init__(*args, **kwargs)
        self._histogram = histogram
        self.min = min
        self.max = max
        self.minclip = minclip
        self.maxclip = maxclip
        self.color = color

    def setHistogram(self, histogram):
        self._histogram = histogram
        self.repaint()

    def setMinimum(self, x):
        self.min = x
        self.repaint()

    def setMaximum(self, x):
        self.max = x
        self.repaint()

    def setClipMinimum(self, x):
        self.minclip = x
        self.repaint()

    def setClipMaximum(self, x):
        self.maxclip = x
        self.repaint()

    def paintEvent(self, event):
        w, h = self.width(), self.height()

        painter = QPainter(self)
        blackpen = QPen(Qt.black, 1)
        nopen = QPen()
        nopen.setStyle(Qt.NoPen)
        redpen = QPen(Qt.red, 1)
        greypen = QPen(Qt.gray, 1)
        painter.setPen(blackpen)
        bfill = QBrush(QColor(0, 0, 0))
        wfill = QBrush(QColor(255, 255, 255))
        painter.fillRect(self.rect(), wfill)
        if self._histogram is not None:
            rect = QRect(0, 0, max(0, self.minclip - self.min)*w/(self.max - self.min), h)
            painter.fillRect(rect, bfill)


            ww = max(0, self.max - self.maxclip)*w/(self.max - self.min)
            rect = QRect(w - ww, 0, ww, h)
            painter.fillRect(rect, bfill)

            fill = QBrush(QColor(*self.color))

            poly = QPolygon()
            H = log(self._histogram/self._histogram.sum())/log(2)
            H = numpy.maximum(H, -25)
            #print(H, H.max())
            for j, k in enumerate(H):
                x = j*w/(len(self._histogram) - 1)
                y = min(h*(k + 4)/(-25 + 4), h)
                poly.append(QPoint(x, y))
                #print(f"({x:.2f}, {y:.2f})")

            poly.append(QPoint(w, h))
            poly.append(QPoint(0, h))

            painter.setPen(nopen)
            painter.setBrush(fill)
            painter.drawPolygon(poly)

class ColorPreview(QWidget):
    def __init__(self, color=QColor(), *args, **kwargs):
        super(ColorPreview, self).__init__(*args, **kwargs)
        self.setColor(color)

    def setColor(self, color):
        self.color = color
        self.repaint()

    def paintEvent(self, event):
        painter = QPainter(self)
        blackpen = QPen(Qt.black, 1)
        fill = QBrush(self.color)
        painter.setPen(blackpen)
        painter.fillRect(self.rect(), fill)
        painter.drawRect(self.rect())

class ChannelEditor(QWidget):
    def __init__(self, color=(0, 0, 0), *args, **kwargs):
        super(ChannelEditor, self).__init__(*args, **kwargs)
        #QWidget.__init__(self, *args, **kwargs)

        layout = QVBoxLayout(self)
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)

        self.color = color

        #self.histogram = QLabel(self)
        self.histogram = Histogram(None, 0, 255, 0, 255, color, self)
        layout.addWidget(self.histogram)
        self.histogram.setMinimumWidth(256)
        self.setMaximumWidth(512)
        self.histogram.setFrameShape(QFrame.Panel)
        self.histogram.setFrameShadow(QFrame.Sunken)

        self.H = None
        self.histogram.setBackgroundRole(QPalette.Base)
        self.histogram.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.histogram.setScaledContents(True)

        spinboxlayout = QHBoxLayout()
        layout.addLayout(spinboxlayout)

        self.minSpinBox = QDoubleSpinBox(self)
        spinboxlayout.addWidget(self.minSpinBox)
        self.minSpinBox.setSingleStep(0.25)
        self.minSpinBox.setDecimals(2)
        self.minSpinBox.setMinimum(0)
        self.minSpinBox.setMaximum(253)
        self.minSpinBox.setValue(0)
        self.minSpinBox.valueChanged.connect(self.minChanged)

        self.minClip = QLabel(self)
        spinboxlayout.addWidget(self.minClip)
        spinboxlayout.addStretch()

        self.gammaSpinBox = QDoubleSpinBox(self)
        spinboxlayout.addWidget(self.gammaSpinBox)
        self.gammaSpinBox.setSingleStep(0.1)
        self.gammaSpinBox.setDecimals(2)
        self.gammaSpinBox.setMinimum(0.25)
        self.gammaSpinBox.setMaximum(4)
        self.gammaSpinBox.setValue(1)

        spinboxlayout.addStretch()

        self.maxClip = QLabel(self)
        spinboxlayout.addWidget(self.maxClip)

        self.maxSpinBox = QDoubleSpinBox(self)
        spinboxlayout.addWidget(self.maxSpinBox)
        self.maxSpinBox.setDecimals(2)
        self.maxSpinBox.setMinimum(2)
        self.maxSpinBox.setMaximum(255)
        self.maxSpinBox.setValue(255)
        self.maxSpinBox.valueChanged.connect(self.maxChanged)

    @pyqtSlot(float)
    def minChanged(self, value):
        self.maxSpinBox.setMinimum(value + 2)
        self.histogram.setClipMinimum(value)
        self.updateClip()

    @pyqtSlot(float)
    def maxChanged(self, value):
        self.minSpinBox.setMaximum(value - 2)
        self.histogram.setClipMaximum(value)
        self.updateClip()

    def updateClip(self):
        if self.H is not None:
            lowerclip = self.H[:int(self.minSpinBox.value()*4 + 0.5)].sum()/self.H.sum()
            upperclip = self.H[int(self.maxSpinBox.value()*4 + 1.5):].sum()/self.H.sum()
            self.minClip.setText("%.4f%%" % (100*lowerclip))
            self.maxClip.setText("%.4f%%" % (100*upperclip))
        else:
            self.minClip.setText("---")
            self.maxClip.setText("---")

    def setHistogram(self, H):
        self.H = H
        self.histogram.setHistogram(H)
        self.updateClip()

#class QLevelsWidget(QWidget):
    #setpreviewlabel = pyqtSignal()
    #loadframe = pyqtSignal(int)
    #def __init__(self, levels):
        #super(QLevelsWidget, self).__init__()
        #self.levels = levels

        #self.rchan = ChannelEditor((128, 0, 0), self)
        #self.gchan = ChannelEditor((0, 128, 0), self)
        #self.bchan = ChannelEditor((0, 0, 128), self)

        #self.rchan.minSpinBox.valueChanged.connect(self.updateZoneValues)
        #self.rchan.gammaSpinBox.valueChanged.connect(self.updateZoneValues)
        #self.rchan.maxSpinBox.valueChanged.connect(self.updateZoneValues)

        #self.gchan.minSpinBox.valueChanged.connect(self.updateZoneValues)
        #self.gchan.gammaSpinBox.valueChanged.connect(self.updateZoneValues)
        #self.gchan.maxSpinBox.valueChanged.connect(self.updateZoneValues)

        #self.bchan.minSpinBox.valueChanged.connect(self.updateZoneValues)
        #self.bchan.gammaSpinBox.valueChanged.connect(self.updateZoneValues)
        #self.bchan.maxSpinBox.valueChanged.connect(self.updateZoneValues)

        #self.previewLabel = None
        #self.currentFrame = None

    #def updatePreview(self):
        #if self.previewLabel is not None and self.currentFrame is not None:
            #R, G, B = numpy.moveaxis(self.currentFrame, 2, 0)

            #J, zone = self.levels.zoneAtPrev(self.n)

            #if zone.transition:
                #k = self.n - zone.prev_start
                #R = zone._R[R, k]
                #G = zone._G[G, k]
                #B = zone._B[B, k]
            #else:
                #R = zone._R[R]
                #G = zone._G[G]
                #B = zone._B[B]

            #A = numpy.moveaxis((R, G, B), 0, 2)
            #im = Image.fromarray(A)
            #qim = im.toqpixmap()
            #self.previewLabel.setPixmap(qim)


    #def updateZoneValues(self):
        #J, zone = self.levels.zoneAtPrev(self.n)
        
        #if not zone.transition:
            #zone.rmin = self.rchan.minSpinBox.value()
            #zone.rgamma = self.rchan.gammaSpinBox.value()
            #zone.rmax = self.rchan.maxSpinBox.value()

            #zone.gmin = self.gchan.minSpinBox.value()
            #zone.ggamma = self.gchan.gammaSpinBox.value()
            #zone.gmax = self.gchan.maxSpinBox.value()

            #zone.bmin = self.bchan.minSpinBox.value()
            #zone.bgamma = self.bchan.gammaSpinBox.value()
            #zone.bmax = self.bchan.maxSpinBox.value()

            #zone.gamma = self.gammaspinbox.value()

            #self.updatePreview()

            #self.rchan.updateHistogram()
            #self.gchan.updateHistogram()
            #self.bchan.updateHistogram()

    ##def loadFrame(self, n=None):
        ##if self._mode < 2:
            ##return super().loadFrame(n)

        ##if n is None:
            ##n = self.slider.value()

        ##try:
            ##frame = next(self.levels.prev.iterFrames(n))
        ##except StopIteration:
            ##return

        ##self.currentFrame = frame.to_rgb().to_ndarray()
        ##im = frame.to_image()
        ##qim = im.toqpixmap()
        ##self.sourceImageLabel.setPixmap(qim)
        ##self.updatePreview()


class QLevels(ZoneDlg):
    zonename = "Levels Zone"
    title = "Levels Editor"
    shadowclass = ShadowZone

    def _prepare(self):
        self.rchan = ChannelEditor((128, 0, 0), self)
        self.gchan = ChannelEditor((0, 128, 0), self)
        self.bchan = ChannelEditor((0, 0, 128), self)

        self.rchan.minSpinBox.valueChanged.connect(self.settingsChanged)
        self.rchan.gammaSpinBox.valueChanged.connect(self.settingsChanged)
        self.rchan.maxSpinBox.valueChanged.connect(self.settingsChanged)

        self.gchan.minSpinBox.valueChanged.connect(self.settingsChanged)
        self.gchan.gammaSpinBox.valueChanged.connect(self.settingsChanged)
        self.gchan.maxSpinBox.valueChanged.connect(self.settingsChanged)

        self.bchan.minSpinBox.valueChanged.connect(self.settingsChanged)
        self.bchan.gammaSpinBox.valueChanged.connect(self.settingsChanged)
        self.bchan.maxSpinBox.valueChanged.connect(self.settingsChanged)

        layout = QHBoxLayout(self)
        self.setLayout(layout)

        llayout = QVBoxLayout()
        rlayout = QVBoxLayout()
        layout.addLayout(llayout)
        layout.addLayout(rlayout)

        llayout.addWidget(self.rchan)
        llayout.addWidget(self.gchan)
        llayout.addWidget(self.bchan)

        self._prepareImageView(rlayout)
        self.imageView.mousePressed.connect(self.setFocus)
        self._prepareStdZoneControls(rlayout)

        self.prevColor = ColorPreview(QColor(), self)
        self.prevColor.setFixedSize(32, 32)
        self.prevColorLabel = QLabel("—", self)

        self.nextColor = ColorPreview(QColor(), self)
        self.nextColor.setFixedSize(32, 32)
        self.nextColorLabel = QLabel("—", self)

        self.transitionCheckBox = QCheckBox("Transition Zone", self)
        self.transitionCheckBox.stateChanged.connect(self.setCurrentZoneTransition)

        self.analyzeBtn = QPushButton("Anal&yze Zone", self)
        self.analyzeBtn.clicked.connect(self.analyzeZone) # 162523

        self.gammaLabel = QLabel("Gamma:", self)

        self.gammaSpinBox = QDoubleSpinBox(self)
        self.gammaSpinBox.setSingleStep(0.1)
        self.gammaSpinBox.setDecimals(2)
        self.gammaSpinBox.setMinimum(0.25)
        self.gammaSpinBox.setMaximum(4)
        self.gammaSpinBox.valueChanged.connect(self.settingsChanged)

        self.suggBtn = QPushButton("&Suggestion", self)
        self.suggBtn.clicked.connect(self.useAutoGamma) # 162523

        sublayout = QHBoxLayout()
        sublayout.addStretch()
        sublayout.addWidget(self.prevColor)
        sublayout.addWidget(self.prevColorLabel)
        sublayout.addStretch()
        sublayout.addWidget(self.nextColor)
        sublayout.addWidget(self.nextColorLabel)
        sublayout.addStretch()
        sublayout.addWidget(self.transitionCheckBox)
        sublayout.addStretch()
        sublayout.addWidget(self.analyzeBtn)
        sublayout.addStretch()
        sublayout.addWidget(self.gammaLabel)
        sublayout.addWidget(self.gammaSpinBox)
        sublayout.addWidget(self.suggBtn)
        sublayout.addStretch()

        rlayout.addLayout(sublayout)

        self._prepareDlgButtons(rlayout)
        self.currentFrame = None
        self.setFocus(None, None)

    @pyqtSlot(float, float)
    def setFocus(self, x, y):
        self._x = x
        self._y = y
        if self.currentFrame is not None and self._x is not None and self._y is not None:
            A = self.currentFrame.to_rgb().to_ndarray()
            h, w, n = A.shape
            X = numpy.arange(w)
            Y = numpy.arange(h)
            X, Y = numpy.meshgrid(X, Y)
            G = numpy.exp(-((X - self._x)**2 + (Y - self._y)**2)/6)
            self._ker = G/G.sum()

        else:
            self._ker = None

        self.updateColors()

    def loadFrame(self, n=None):
        super().loadFrame(n)
        self.updateColors()

    def generatePreview(self, n):
        start = self.shadow.getIterStart(n)
        self.currentFrame = frame = next(self.shadow.parent.prev.iterFrames(start, whence="framenumber"))

        prev_start = self.shadow.parent.prev.frameIndexFromPts(frame.pts)
        framecount = self.shadow.prev_end - prev_start

        for frame in self.shadow.processFrames([frame], prev_start):
            if frame.pts >= self.shadow.pts[n - self.shadow.dest_start]:
                return frame

        return VideoFrame(width=self.shadow.parent.width, height=self.shadow.parent.height)


    def updateColors(self):
        if self.currentFrame is not None and self._x is not None and self._y is not None and self._ker is not None:
            A = self.currentFrame.to_rgb().to_ndarray()
            avg = numpy.int0((numpy.moveaxis(A, 2, 0)*self._ker).sum(axis=(1, 2)) + 0.5)
            R, G, B = avg

            self.prevColor.setColor(QColor(R, G, B))
            self.prevColorLabel.setText(f"({R}, {G}, {B})")

            N = numpy.arange(256, dtype=numpy.float64)
            n = self.slider.value()

            if self.transitionCheckBox.checkState() and self.zone.prev is not None and self.zone.next is not None:
                t = (n - self.zone.prev_start + 1)/(self.zone.prev_framecount + 1)
                rmin = (1 - t)*self.zone.prev.rmin + t*self.zone.next.rmin
                gmin = (1 - t)*self.zone.prev.gmin + t*self.zone.next.gmin
                bmin = (1 - t)*self.zone.prev.bmin + t*self.zone.next.bmin

                rmax = (1 - t)*self.zone.prev.rmax + t*self.zone.next.rmax
                gmax = (1 - t)*self.zone.prev.gmax + t*self.zone.next.gmax
                bmax = (1 - t)*self.zone.prev.bmax + t*self.zone.next.bmax

                rgamma = (1 - t)*self.zone.prev.rgamma + t*self.zone.next.rgamma
                ggamma = (1 - t)*self.zone.prev.ggamma + t*self.zone.next.ggamma
                bgamma = (1 - t)*self.zone.prev.bgamma + t*self.zone.next.bgamma

                gamma = (1 - t)*self.zone.prev.gamma + t*self.zone.next.gamma
            else:
                rmin = self.rchan.minSpinBox.value()
                gmin = self.gchan.minSpinBox.value()
                bmin = self.bchan.minSpinBox.value()
                rmax = self.rchan.maxSpinBox.value()
                gmax = self.gchan.maxSpinBox.value()
                bmax = self.bchan.maxSpinBox.value()
                rgamma = self.rchan.gammaSpinBox.value()
                ggamma = self.gchan.gammaSpinBox.value()
                bgamma = self.bchan.gammaSpinBox.value()
                gamma = self.gammaSpinBox.value()

            RR = (N.clip(min=rmin, max=rmax) - rmin)/(rmax - rmin)
            RR = 1 - (1 - RR)**(rgamma*gamma)
            RR = numpy.uint8((256*RR).clip(max=255) + 0.5)
            GG = (N.clip(min=gmin, max=gmax) - gmin)/(gmax - gmin)
            GG = 1 - (1 - GG)**(ggamma*gamma)
            GG = numpy.uint8((256*GG).clip(max=255) + 0.5)
            BB = (N.clip(min=bmin, max=bmax) - bmin)/(bmax - bmin)
            BB = 1 - (1 - BB)**(bgamma*gamma)
            BB = numpy.uint8((256*BB).clip(max=255) + 0.5)

            R = RR[R]
            G = GG[G]
            B = BB[B]

            self.nextColor.setColor(QColor(R, G, B))
            self.nextColorLabel.setText(f"({R}, {G}, {B})")


    def analyzeZone(self):
        dlg = ZoneAnalysis(self.shadow, self)
        dlg.exec_()

        if self.shadow.histogram is not None:
            self.rchan.setHistogram(self.shadow.histogram[0])
            self.gchan.setHistogram(self.shadow.histogram[1])
            self.bchan.setHistogram(self.shadow.histogram[2])

            self.suggBtn.setEnabled(True)
            gamma = self.autogamma()
            self.suggBtn.setText(f"Suggestion: {gamma:.2f}")

    def autogamma(self):
        zone = self.shadow
        a = numpy.arange(0, 256, 0.25)
        I = -numpy.log(1-a/256)
        r, g, b = self.rchan.minSpinBox.value(), self.gchan.minSpinBox.value(), self.bchan.minSpinBox.value()
        R, G, B = self.rchan.maxSpinBox.value(), self.gchan.maxSpinBox.value(), self.bchan.maxSpinBox.value()
        rg, gg, bg = self.rchan.gammaSpinBox.value(), self.gchan.gammaSpinBox.value(), self.bchan.gammaSpinBox.value()

        IR = -numpy.log(1-(a.clip(min=r, max=R+0.75) - r)/(R+1-r))*rg
        IG = -numpy.log(1-(a.clip(min=g, max=G+0.75) - g)/(G+1-g))*gg
        IB = -numpy.log(1-(a.clip(min=b, max=B+0.75) - b)/(B+1-b))*bg
        gamma = ((I*zone.histogram[0]).sum() + (I*zone.histogram[1]).sum() + (I*zone.histogram[2]).sum())/((IR*zone.histogram[0]).sum() + (IG*zone.histogram[1]).sum() + (IB*zone.histogram[2]).sum())
        return float(gamma)

    def useAutoGamma(self):
        gamma = self.autogamma()
        self.gammaSpinBox.setValue(gamma)

    def setCurrentZoneTransition(self, state):
        flag = state == Qt.Unchecked

        self.rchan.setEnabled(flag)
        self.gchan.setEnabled(flag)
        self.bchan.setEnabled(flag)
        self.gammaSpinBox.setEnabled(flag)
        self.settingsChanged()

    def _loadZone(self):
        zone = self.zone

        if zone.transition:
            self.transitionCheckBox.blockSignals(True)
            self.transitionCheckBox.setChecked(True)
            self.transitionCheckBox.blockSignals(False)
            self.transitionCheckBox.setEnabled(True)
            self.rchan.setEnabled(False)
            self.gchan.setEnabled(False)
            self.bchan.setEnabled(False)
            self.gammaSpinBox.setEnabled(False)
            self.rchan.setHistogram(None)
            self.gchan.setHistogram(None)
            self.bchan.setHistogram(None)

        else:
            self.transitionCheckBox.blockSignals(True)
            self.transitionCheckBox.setChecked(False)
            self.transitionCheckBox.blockSignals(False)
            self.transitionCheckBox.setEnabled(zone not in (zone.parent.start, zone.parent.end) and 
                                               True not in (zone.prev.transition, zone.next.transition))

            self.rchan.setEnabled(True)
            self.gchan.setEnabled(True)
            self.bchan.setEnabled(True)
            self.gammaSpinBox.setEnabled(True)

            self.rchan.minSpinBox.blockSignals(True)
            self.rchan.minSpinBox.setValue(zone.rmin)
            self.rchan.histogram.setClipMinimum(zone.rmin)
            self.rchan.minSpinBox.blockSignals(False)

            self.rchan.maxSpinBox.blockSignals(True)
            self.rchan.maxSpinBox.setValue(zone.rmax)
            self.rchan.histogram.setClipMaximum(zone.rmax)
            self.rchan.maxSpinBox.blockSignals(False)

            self.rchan.gammaSpinBox.blockSignals(True)
            self.rchan.gammaSpinBox.setValue(zone.rgamma)
            self.rchan.gammaSpinBox.blockSignals(False)

            self.gchan.minSpinBox.blockSignals(True)
            self.gchan.minSpinBox.setValue(zone.gmin)
            self.gchan.histogram.setClipMinimum(zone.gmin)
            self.gchan.minSpinBox.blockSignals(False)

            self.gchan.maxSpinBox.blockSignals(True)
            self.gchan.maxSpinBox.setValue(zone.gmax)
            self.gchan.histogram.setClipMaximum(zone.gmax)
            self.gchan.maxSpinBox.blockSignals(False)

            self.gchan.gammaSpinBox.blockSignals(True)
            self.gchan.gammaSpinBox.setValue(zone.ggamma)
            self.gchan.gammaSpinBox.blockSignals(False)

            self.bchan.minSpinBox.blockSignals(True)
            self.bchan.minSpinBox.setValue(zone.bmin)
            self.bchan.histogram.setClipMinimum(zone.bmin)
            self.bchan.minSpinBox.blockSignals(False)

            self.bchan.maxSpinBox.blockSignals(True)
            self.bchan.maxSpinBox.setValue(zone.bmax)
            self.bchan.histogram.setClipMaximum(zone.bmax)
            self.bchan.maxSpinBox.blockSignals(False)

            self.bchan.gammaSpinBox.blockSignals(True)
            self.bchan.gammaSpinBox.setValue(zone.bgamma)
            self.bchan.gammaSpinBox.blockSignals(False)

            self.gammaSpinBox.blockSignals(True)
            self.gammaSpinBox.setValue(zone.gamma)
            self.gammaSpinBox.blockSignals(False)

            if zone.histogram is not None:
                self.rchan.setHistogram(zone.histogram[0])
                self.gchan.setHistogram(zone.histogram[1])
                self.bchan.setHistogram(zone.histogram[2])
                self.suggBtn.setEnabled(True)
                gamma = self.autogamma()
                self.suggBtn.setText(f"Suggestion: {gamma:.2f}")

            else:
                self.rchan.setHistogram(None)
                self.gchan.setHistogram(None)
                self.bchan.setHistogram(None)
                self.suggBtn.setEnabled(False)
                self.suggBtn.setText("No Suggestion")

    def updateZoneValues(self):
        self.shadow.transition = bool(self.transitionCheckBox.checkState())

        if self.shadow is not None and not self.shadow.transition:
            self.shadow.rmin = self.rchan.minSpinBox.value()
            self.shadow.rgamma = self.rchan.gammaSpinBox.value()
            self.shadow.rmax = self.rchan.maxSpinBox.value()

            self.shadow.gmin = self.gchan.minSpinBox.value()
            self.shadow.ggamma = self.gchan.gammaSpinBox.value()
            self.shadow.gmax = self.gchan.maxSpinBox.value()

            self.shadow.bmin = self.bchan.minSpinBox.value()
            self.shadow.bgamma = self.bchan.gammaSpinBox.value()
            self.shadow.bmax = self.bchan.maxSpinBox.value()

            self.shadow.gamma = self.gammaSpinBox.value()

            if self.shadow.histogram is not None:
                self.rchan.setHistogram(self.shadow.histogram[0])
                self.gchan.setHistogram(self.shadow.histogram[1])
                self.bchan.setHistogram(self.shadow.histogram[2])

                self.suggBtn.setEnabled(True)
                gamma = self.autogamma()
                self.suggBtn.setText(f"Suggestion: {gamma:.2f}")

        #self.settingsApplied.emit()
        self.loadFrame()

    def settingsChanged(self):
        self.updateColors()
        self.updateZoneValues()
        self.isModified()

    def apply(self):
        self.updateZoneValues()
        super().apply()

    #def _prepareDlgButtons(self, layout=None, index=None):
        #if layout is None:
            #layout = self.layout()

        #self.okayBtn = QPushButton("&OK", self)
        #self.okayBtn.setDefault(True)
        #self.okayBtn.clicked.connect(self.applyAndClose)
        #self.applyBtn = QPushButton("&Apply", self)
        #self.applyBtn.clicked.connect(self.apply)
        #self.closeBtn = QPushButton("&Close", self)
        #self.closeBtn.setDefault(True)
        #self.closeBtn.clicked.connect(self.close)

        #sublayout = QHBoxLayout()
        #sublayout.addStretch()
        #sublayout.addWidget(self.okayBtn)
        #sublayout.addWidget(self.applyBtn)
        #sublayout.addWidget(self.closeBtn)

        #if isinstance(layout, QGridLayout):
            #layout.addLayout(sublayout, *index)

        #elif index is not None:
            #layout.insertLayout(index, sublayout)

        #else:
            #layout.addLayout(sublayout)

class ZoneAnalysis(QProgressDialog):
    progressstarted = pyqtSignal(int)
    progress = pyqtSignal(int)
    progresscomplete = pyqtSignal()
    cancelled = pyqtSignal()

    def __init__(self, zone, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAutoClose(True)
        self.setAutoReset(False)
        self.setWindowTitle("Analyzing Zone...")
        self.setLabel(QLabel("Analyzing Zone..."))

        self.cancelevent = threading.Event()
        self.cancelButton = QPushButton("&Cancel")
        self.setCancelButton(self.cancelButton)
        self.cancelButton.clicked.connect(self.cancel)

        self.stopped = False

        self.zone = zone

        self.setMaximum(zone.framecount)
        self.progress.connect(self.updateValue)
        self.progresscomplete.connect(self.progressComplete)

        self.thread = None

    def exec_(self):
        self.thread = threading.Thread(target=self.zone.analyzeFrames,
                             kwargs=dict(notifyprogress=self.progress.emit, notifyfinish=self.progresscomplete.emit, cancelled=self.cancelevent))
        self.thread.start()
        return super().exec_()

    def updateValue(self, value):
        if value > self.value():
            self.setValue(value)

    def progressComplete(self):
        self.done(1)
        self.close()

    def cancel(self):
        self.cancelevent.set()

        if self.thread is not None:
            self.thread.join()

        self.setValue(0)
        super().cancel()

class LevelsCol(ZoneCol):
    bgcolor = QColor(255, 128, 128)
    bgcoloralt = QColor(255, 255, 255)
    fgcolor = QColor(0, 0, 0)
    fgcoloralt = QColor(160, 160, 160)
    headerdisplay = "Levels"

    def createContextMenu(self, table, index, obj):
        menu = ZoneCol.createContextMenu(self, table, index, obj)
        menu.addSeparator()
        configure = QAction("Configure zone...", table, triggered=partial(self.createDlg, table=table, index=index))
        menu.addAction(configure)
        return menu

    def createDlg(self, table, index):
        J, zone = self.filter.zoneAt(index.data(Qt.UserRole))
        dlg = QLevels(zone, table)
        dlg.slider.setValue(self.filter.cumulativeIndexMap[index.data(Qt.UserRole)])

        if dlg.exec_():
            tm = table.model()
            idx1 = tm.index(0, 0)
            idx2 = tm.index(self.rowCount()-1, self.columnCount()-1)
            tm.dataChanged.emit(idx1, idx2)


    #def display(self, obj, index):
        #K, zone = self.filter.zoneAt(index)
        #if zone.transition:
            #return "%d Transition" % K
        #return "{K} ({zone.rmin:.2f}, {zone.rgamma:.2f}, {zone.rmax:.2f}), ({zone.gmin:.2f}, {zone.ggamma:.2f}, {zone.gmax:.2f}), ({zone.bmin:.2f}, {zone.bgamma:.2f}, {zone.bmax:.2f}), {zone.gamma:.2f}".format(K=K, zone=zone)

    #def bgdata(self, obj, index):
        #K, zone = self.filter.zoneAt(index)
        #if index == zone.src_start:
            #return self.bgcolor1
        #return self.bgcolor2

    #def fgdata(self, obj, index):
        #K, zone = self.filter.zoneAt(index)
        #if index == zone.src_start:
            #return self.fgcolor1
        #return self.fgcolor2