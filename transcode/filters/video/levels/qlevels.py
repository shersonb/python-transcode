from PyQt5.QtGui import (QPainter, QPalette, QColor, QBrush, QPen, QPolygon,
                         QPainterPath)
from PyQt5.QtCore import Qt, QPoint, QRect, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (QAction, QProgressDialog, QVBoxLayout,
                             QHBoxLayout, QPushButton, QCheckBox, QLabel,
                             QWidget, QFrame, QSizePolicy, QDoubleSpinBox)

from functools import partial
from numpy import (log, arange, int0, maximum, meshgrid, exp, moveaxis,
                   uint8, float64, ndarray)
import threading

from . import Levels
from transcode.pyqtgui.qframetablecolumn import ZoneCol
from transcode.pyqtgui.qzones import ZoneDlg
import sys
import traceback


class Histogram(QLabel):
    def __init__(self, histogram=None, min=0, max=256, gamma=1,
                 minclip=0, maxclip=255, color=(0, 0, 0), *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._histogram = histogram
        self.min = min
        self.max = max
        self.gamma = gamma
        self.minclip = minclip
        self.maxclip = maxclip
        self.color = color

    def setHistogram(self, histogram):
        self._histogram = histogram
        self.update()

    def setMinimum(self, x):
        self.min = x
        self.update()

    def setMaximum(self, x):
        self.max = x
        self.update()

    def setGamma(self, x):
        self.gamma = x
        self.update()

    def setClipMinimum(self, x):
        self.minclip = x
        self.update()

    def setClipMaximum(self, x):
        self.maxclip = x
        self.update()

    def paintEvent(self, event):
        w, h = self.width(), self.height()

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        blackpen = QPen(Qt.black, 1)
        nopen = QPen()
        nopen.setStyle(Qt.NoPen)
        greypen = QPen(Qt.gray, 1)
        painter.setPen(blackpen)
        nofill = QBrush()
        bfill = QBrush(QColor(0, 0, 0))
        wfill = QBrush(QColor(255, 255, 255))

        if self._histogram is not None:
            painter.fillRect(self.rect(), wfill)
            rect = QRect(0, 0, max(0, self.minclip - self.min)
                         * w/(self.max - self.min), h)
            painter.fillRect(rect, bfill)

            ww = max(0, self.max - self.maxclip)*w/(self.max - self.min)
            rect = QRect(w - ww, 0, ww, h)
            painter.fillRect(rect, bfill)

            fill = QBrush(QColor(*self.color))

            poly = QPolygon()
            path = QPainterPath()
            pathstarted = False

            H = log(self._histogram/self._histogram.sum())/log(2)
            H = maximum(H, -25)

            m = self.minclip/255
            M = self.maxclip/255

            for j, k in enumerate(H):
                x = j*w/(len(self._histogram) - 1)
                y = min(h*(k + 4)/(-25 + 4), h)
                poly.append(QPoint(x, y))

                u = j/len(self._histogram)

                if (isinstance(m, ndarray)
                        or isinstance(M, ndarray)
                        or isinstance(self.gamma, ndarray)):
                    continue

                if m <= u <= M:
                    v = 1 - (1 - (u - m)/(M - m))**self.gamma

                    if u < M or self.gamma >= 1:
                        dvdu = self.gamma * \
                            (1 - (u - m)/(M - m))**(self.gamma - 1)/(M - m)

                    else:
                        dvdu = 1

                    if pathstarted:
                        path.lineTo(v*w, y - log(dvdu)/log(2)/(-25+4))

                    else:
                        path.moveTo(v*w, y - log(dvdu)/log(2)/(-25+4))
                        pathstarted = True

            poly.append(QPoint(w, h))
            poly.append(QPoint(0, h))

            painter.setPen(nopen)
            painter.setBrush(fill)
            painter.drawPolygon(poly)
            painter.setPen(greypen)
            painter.setBrush(nofill)
            painter.drawPath(path)


class ColorPreview(QWidget):
    def __init__(self, color=QColor(), *args, **kwargs):
        super(ColorPreview, self).__init__(*args, **kwargs)
        self.setColor(color)

    def setColor(self, color):
        self.color = color
        self.update()

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

        layout = QVBoxLayout(self)
        self.setLayout(layout)
        layout.setContentsMargins(0, 0, 0, 0)

        self.color = color

        self.histogram = Histogram(None, 0, 255, 1, 0, 255, color, self)
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
            lowerclip = self.H[:int(
                self.minSpinBox.value()*4 + 0.5)].sum()/self.H.sum()
            upperclip = self.H[int(
                self.maxSpinBox.value()*4 + 1.5):].sum()/self.H.sum()
            self.minClip.setText("%.4f%%" % (100*lowerclip))
            self.maxClip.setText("%.4f%%" % (100*upperclip))
        else:
            self.minClip.setText("---")
            self.maxClip.setText("---")

    def setHistogram(self, H):
        self.H = H
        self.histogram.setHistogram(H)
        self.updateClip()


class QLevels(ZoneDlg):
    allowedtypes = ("video",)
    zonename = "Levels Zone"
    title = "Levels Editor"

    def createNewFilterInstance(self):
        return Levels()

    def _createControls(self):
        self.setWindowTitle("Configure Levels Zones")

        self.rchan = ChannelEditor((128, 0, 0), self)
        self.gchan = ChannelEditor((0, 128, 0), self)
        self.bchan = ChannelEditor((0, 0, 128), self)

        self.rchan.minSpinBox.valueChanged.connect(self.widgetValuesChanged)
        self.rchan.gammaSpinBox.valueChanged.connect(self.widgetValuesChanged)
        self.rchan.maxSpinBox.valueChanged.connect(self.widgetValuesChanged)

        self.gchan.minSpinBox.valueChanged.connect(self.widgetValuesChanged)
        self.gchan.gammaSpinBox.valueChanged.connect(self.widgetValuesChanged)
        self.gchan.maxSpinBox.valueChanged.connect(self.widgetValuesChanged)

        self.bchan.minSpinBox.valueChanged.connect(self.widgetValuesChanged)
        self.bchan.gammaSpinBox.valueChanged.connect(self.widgetValuesChanged)
        self.bchan.maxSpinBox.valueChanged.connect(self.widgetValuesChanged)

        layout = QHBoxLayout(self)
        self.setLayout(layout)

        llayout = QVBoxLayout()
        rlayout = QVBoxLayout()
        layout.addLayout(llayout)
        layout.addLayout(rlayout)

        llayout.addWidget(self.rchan)
        llayout.addWidget(self.gchan)
        llayout.addWidget(self.bchan)

        self.sourceWidget = QWidget(self)
        self.sourceSelection = self.createSourceControl(self.sourceWidget)
        self.sourceSelection.currentDataChanged.connect(self.setFilterSource)

        srclayout = QHBoxLayout()
        srclayout.addWidget(QLabel("Source: ", self.sourceWidget))
        srclayout.addWidget(self.sourceSelection)

        self.sourceWidget.setLayout(srclayout)
        rlayout.addWidget(self.sourceWidget)

        self._createImageView(rlayout)
        self.imageView.mousePressed.connect(self.setFocus)

        self._createZoneNavControls(rlayout)
        self._createZoneControls(rlayout)
        self._createZoneButtons(rlayout)
        self._createGlobalControls(rlayout)
        self._createDlgButtons(rlayout)

    def _createZoneControls(self, layout=None, index=None):
        if layout is None:
            layout = self.layout()

        self.prevColor = ColorPreview(QColor(), self)
        self.prevColor.setFixedSize(32, 32)
        self.prevColorLabel = QLabel("—", self)

        self.nextColor = ColorPreview(QColor(), self)
        self.nextColor.setFixedSize(32, 32)
        self.nextColorLabel = QLabel("—", self)

        self.transitionCheckBox = QCheckBox("Transition Zone", self)
        self.transitionCheckBox.stateChanged.connect(
            self.setCurrentZoneTransition)

        self.analyzeBtn = QPushButton("Anal&yze Zone", self)
        self.analyzeBtn.clicked.connect(self.analyzeZone)  # 162523

        self.gammaLabel = QLabel("Gamma:", self)

        self.gammaSpinBox = QDoubleSpinBox(self)
        self.gammaSpinBox.setSingleStep(0.1)
        self.gammaSpinBox.setDecimals(2)
        self.gammaSpinBox.setMinimum(0.25)
        self.gammaSpinBox.setMaximum(4)
        self.gammaSpinBox.valueChanged.connect(self.widgetValuesChanged)

        self.suggBtn = QPushButton("&Suggestion", self)
        self.suggBtn.clicked.connect(self.useAutoGamma)  # 162523

        inpLabel = QLabel("Input", self)
        outLabel = QLabel("Output", self)

        self.redAvgIntensIn = QLabel("Avg Red Intensity: —", self)
        self.greenAvgIntensIn = QLabel("Avg Green Intensity: —", self)
        self.blueAvgIntensIn = QLabel("Avg Blue Intensity: —", self)

        self.redAvgIntensOut = QLabel("Avg Red Intensity: —", self)
        self.greenAvgIntensOut = QLabel("Avg Green Intensity: —", self)
        self.blueAvgIntensOut = QLabel("Avg Blue Intensity: —", self)

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

        layout.addLayout(sublayout)

        sublayout = QHBoxLayout()
        sublayout.addStretch()
        sublayout.addWidget(inpLabel)
        sublayout.addStretch()
        sublayout.addWidget(self.redAvgIntensIn)
        sublayout.addStretch()
        sublayout.addWidget(self.greenAvgIntensIn)
        sublayout.addStretch()
        sublayout.addWidget(self.blueAvgIntensIn)
        sublayout.addStretch()

        layout.addLayout(sublayout)

        sublayout = QHBoxLayout()
        sublayout.addStretch()
        sublayout.addWidget(outLabel)
        sublayout.addStretch()
        sublayout.addWidget(self.redAvgIntensOut)
        sublayout.addStretch()
        sublayout.addWidget(self.greenAvgIntensOut)
        sublayout.addStretch()
        sublayout.addWidget(self.blueAvgIntensOut)
        sublayout.addStretch()

        layout.addLayout(sublayout)

        self.currentFrame = None
        self.setFocus(None, None)

    @pyqtSlot(float, float)
    def setFocus(self, x, y):
        self._x = x
        self._y = y

        if (self.currentFrame is not None
                and self._x is not None
                and self._y is not None):
            A = self.currentFrame.to_rgb().to_ndarray()
            h, w, n = A.shape
            X = arange(w)
            Y = arange(h)
            X, Y = meshgrid(X, Y)
            G = exp(-((X - self._x)**2 + (Y - self._y)**2)/6)
            self._ker = G/G.sum()

        else:
            self._ker = None

        self.updateColors()

    def loadFrame(self, n, t):
        super().loadFrame(n, t)

        try:
            self.updateColors()

        except Exception:
            for line in traceback.format_exception(*sys.exc_info()):
                print(line, file=sys.stderr, end="")

    def generatePreview(self, n):
        self.currentFrame = next(
            self.filtercopy.prev.iterFrames(n, whence="framenumber"))

        return super().generatePreview(n)

    def updateColors(self):
        if (self.currentFrame is not None
                and self._x is not None
                and self._y is not None
                and self._ker is not None):
            A = self.currentFrame.to_rgb().to_ndarray()
            avg = int0(
                (moveaxis(A, 2, 0)*self._ker).sum(axis=(1, 2)) + 0.5)
            R, G, B = avg

            self.prevColor.setColor(QColor(R, G, B))
            self.prevColorLabel.setText(f"({R}, {G}, {B})")

            N = arange(256, dtype=float64)
            n = self.slider.slider.value()

            if (self.transitionCheckBox.checkState()
                    and self.zonecopy.prev is not None
                    and self.zonecopy.next is not None):
                t = (n - self.zonecopy.prev_start + 1) / \
                    (self.zonecopy.prev_framecount + 1)
                rmin = (1 - t)*self.zonecopy.prev.rmin + \
                    t*self.zonecopy.next.rmin
                gmin = (1 - t)*self.zonecopy.prev.gmin + \
                    t*self.zonecopy.next.gmin
                bmin = (1 - t)*self.zonecopy.prev.bmin + \
                    t*self.zonecopy.next.bmin

                rmax = (1 - t)*self.zonecopy.prev.rmax + \
                    t*self.zonecopy.next.rmax
                gmax = (1 - t)*self.zonecopy.prev.gmax + \
                    t*self.zonecopy.next.gmax
                bmax = (1 - t)*self.zonecopy.prev.bmax + \
                    t*self.zonecopy.next.bmax

                rgamma = (1 - t)*self.zonecopy.prev.rgamma + \
                    t*self.zonecopy.next.rgamma
                ggamma = (1 - t)*self.zonecopy.prev.ggamma + \
                    t*self.zonecopy.next.ggamma
                bgamma = (1 - t)*self.zonecopy.prev.bgamma + \
                    t*self.zonecopy.next.bgamma

                gamma = (1 - t)*self.zonecopy.prev.gamma + \
                    t*self.zonecopy.next.gamma
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
            RR = uint8((256*RR).clip(max=255) + 0.5)
            GG = (N.clip(min=gmin, max=gmax) - gmin)/(gmax - gmin)
            GG = 1 - (1 - GG)**(ggamma*gamma)
            GG = uint8((256*GG).clip(max=255) + 0.5)
            BB = (N.clip(min=bmin, max=bmax) - bmin)/(bmax - bmin)
            BB = 1 - (1 - BB)**(bgamma*gamma)
            BB = uint8((256*BB).clip(max=255) + 0.5)

            R = RR[R]
            G = GG[G]
            B = BB[B]

            self.nextColor.setColor(QColor(R, G, B))
            self.nextColorLabel.setText(f"({R}, {G}, {B})")

    def analyzeZone(self):
        dlg = ZoneAnalysis(self.zonecopy, self)
        dlg.exec_()
        self.zoneModified()

        if self.zonecopy.histogram is not None:
            self.rchan.setHistogram(self.zonecopy.histogram[0])
            self.gchan.setHistogram(self.zonecopy.histogram[1])
            self.bchan.setHistogram(self.zonecopy.histogram[2])

            self.suggBtn.setEnabled(True)
            gamma = self.autogamma()
            self.suggBtn.setText(f"Suggestion: {gamma:.2f}")

    def autogamma(self):
        zone = self.zonecopy
        a = arange(0, 256, 0.25)
        Ia = -log(1-a/256)
        r, g, b = self.rchan.minSpinBox.value(
        ), self.gchan.minSpinBox.value(), self.bchan.minSpinBox.value()
        R, G, B = self.rchan.maxSpinBox.value(
        ), self.gchan.maxSpinBox.value(), self.bchan.maxSpinBox.value()
        rg, gg, bg = self.rchan.gammaSpinBox.value(
        ), self.gchan.gammaSpinBox.value(), self.bchan.gammaSpinBox.value()

        IR = -log(1-(a.clip(min=r, max=R+0.75) - r)/(R+1-r))*rg
        IG = -log(1-(a.clip(min=g, max=G+0.75) - g)/(G+1-g))*gg
        IB = -log(1-(a.clip(min=b, max=B+0.75) - b)/(B+1-b))*bg

        gamma = (((Ia*zone.histogram[0]).sum()
                  + (Ia*zone.histogram[1]).sum()
                  + (Ia*zone.histogram[2]).sum())
                 / ((IR*zone.histogram[0]).sum()
                    + (IG*zone.histogram[1]).sum()
                    + (IB*zone.histogram[2]).sum()))
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
        self.widgetValuesChanged()

    def _resetZoneControls(self):
        zone = self.zonecopy

        if self.zonecopy.transition:
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
            self.transitionCheckBox.setEnabled(
                self.zone not in (
                    self.zone.parent.start, self.zone.parent.end)
                and not (
                    self.zone.prev.transition or self.zone.next.transition))

            self.rchan.setEnabled(True)
            self.gchan.setEnabled(True)
            self.bchan.setEnabled(True)
            self.gammaSpinBox.setEnabled(True)

            self.rchan.minSpinBox.blockSignals(True)
            self.rchan.minSpinBox.setValue(zone.rmin)
            self.rchan.histogram.setClipMinimum(zone.rmin)
            self.rchan.histogram.setGamma(zone.rgamma*zone.gamma)
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
            self.gchan.histogram.setGamma(zone.ggamma*zone.gamma)
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
            self.bchan.histogram.setGamma(zone.bgamma*zone.gamma)
            self.bchan.maxSpinBox.blockSignals(False)

            self.bchan.gammaSpinBox.blockSignals(True)
            self.bchan.gammaSpinBox.setValue(zone.bgamma)
            self.bchan.gammaSpinBox.blockSignals(False)

            self.gammaSpinBox.blockSignals(True)
            self.gammaSpinBox.setValue(zone.gamma)
            self.gammaSpinBox.blockSignals(False)

        self.updateStats()

    def updateStats(self):
        if self.zonecopy.histogram is not None:
            R, G, B = self.zonecopy.histogram
            self.rchan.setHistogram(R)
            self.gchan.setHistogram(G)
            self.bchan.setHistogram(B)

            self.suggBtn.setEnabled(True)
            gamma = self.autogamma()
            self.suggBtn.setText(f"Suggestion: {gamma:.2f}")

            if not self.zonecopy.transition:
                N = arange(0, 256, 0.25)
                Ia = -log(1 - N/256)/log(2)

                rmin = self.zonecopy.rmin
                rmax = self.zonecopy.rmax
                Nr = (N.clip(min=rmin, max=rmax - 0.25) - rmin)/(rmax - rmin)
                Ir = -self.zonecopy.gamma * \
                    self.zonecopy.rgamma*log(1 - Nr)/log(2)

                gmin = self.zonecopy.gmin
                gmax = self.zonecopy.gmax
                Ng = (N.clip(min=gmin, max=gmax - 0.25) - gmin)/(gmax - gmin)
                Ig = -self.zonecopy.gamma * \
                    self.zonecopy.ggamma*log(1 - Ng)/log(2)

                bmin = self.zonecopy.bmin
                bmax = self.zonecopy.bmax
                Nb = (N.clip(min=bmin, max=bmax - 0.25) - bmin)/(bmax - bmin)
                Ib = -self.zonecopy.gamma * \
                    self.zonecopy.bgamma*log(1 - Nb)/log(2)

                self.redAvgIntensIn.setText(
                    f"Avg Red Intensity: {(Ia*R).sum()/R.sum():.2f}")
                self.greenAvgIntensIn.setText(
                    f"Avg Green Intensity: {(Ia*G).sum()/G.sum():.2f}")
                self.blueAvgIntensIn.setText(
                    f"Avg Blue Intensity: {(Ia*B).sum()/B.sum():.2f}")

                self.redAvgIntensOut.setText(
                    f"Avg Red Intensity: {(Ir*R).sum()/R.sum():.2f}")
                self.greenAvgIntensOut.setText(
                    f"Avg Green Intensity: {(Ig*G).sum()/G.sum():.2f}")
                self.blueAvgIntensOut.setText(
                    f"Avg Blue Intensity: {(Ib*B).sum()/B.sum():.2f}")

            else:
                self.redAvgIntensOut.setText("Avg Red Intensity: —")
                self.greenAvgIntensOut.setText("Avg Green Intensity: —")
                self.blueAvgIntensOut.setText("Avg Blue Intensity: —")

                self.redAvgIntensIn.setText("Avg Red Intensity: —")
                self.greenAvgIntensIn.setText("Avg Green Intensity: —")
                self.blueAvgIntensIn.setText("Avg Blue Intensity: —")

        else:
            self.rchan.setHistogram(None)
            self.gchan.setHistogram(None)
            self.bchan.setHistogram(None)

            self.suggBtn.setEnabled(False)
            self.suggBtn.setText("No Suggestion")

            self.redAvgIntensOut.setText("Avg Red Intensity: —")
            self.greenAvgIntensOut.setText("Avg Green Intensity: —")
            self.blueAvgIntensOut.setText("Avg Blue Intensity: —")

            self.redAvgIntensIn.setText("Avg Red Intensity: —")
            self.greenAvgIntensIn.setText("Avg Green Intensity: —")
            self.blueAvgIntensIn.setText("Avg Blue Intensity: —")

    def updateZoneValues(self):
        self.zonecopy.transition = bool(self.transitionCheckBox.checkState())

        if self.zonecopy is not None and not self.zonecopy.transition:
            self.zonecopy.rmin = self.rchan.minSpinBox.value()
            self.zonecopy.rgamma = self.rchan.gammaSpinBox.value()
            self.zonecopy.rmax = self.rchan.maxSpinBox.value()

            self.zonecopy.gmin = self.gchan.minSpinBox.value()
            self.zonecopy.ggamma = self.gchan.gammaSpinBox.value()
            self.zonecopy.gmax = self.gchan.maxSpinBox.value()

            self.zonecopy.bmin = self.bchan.minSpinBox.value()
            self.zonecopy.bgamma = self.bchan.gammaSpinBox.value()
            self.zonecopy.bmax = self.bchan.maxSpinBox.value()

            self.zonecopy.gamma = self.gammaSpinBox.value()

        self.updateStats()
        self.loadFrame(self.slider.slider.value(),
                       self.slider.currentTime.time())

    def widgetValuesChanged(self):
        self.updateColors()
        self.updateZoneValues()
        self.zoneModified()

        zone = self.zonecopy
        self.rchan.histogram.setGamma(zone.rgamma*zone.gamma)
        self.gchan.histogram.setGamma(zone.ggamma*zone.gamma)
        self.bchan.histogram.setGamma(zone.bgamma*zone.gamma)

    def apply(self):
        self.updateZoneValues()
        super().apply()


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
        self.setMinimumWidth(320)
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
        self.thread = threading.Thread(
            target=self.zone.analyzeFrames,
            kwargs=dict(
                notifyprogress=self.progress.emit,
                notifyfinish=self.progresscomplete.emit,
                cancelled=self.cancelevent))

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

        configure = QAction(
            "Analyze selected zone(s)...", table,
            triggered=partial(self.analyzeZones, table=table))

        menu.addAction(configure)

        configure = QAction(
            "Configure zone...", table,
            triggered=partial(self.createDlg, table=table, index=index))

        menu.addAction(configure)
        return menu

    def analyzeZones(self, table):
        sm = table.selectionModel()
        selected = {table.model().data(idx, Qt.UserRole)
                    for idx in sm.selectedIndexes()}

        zones = []

        for k in sorted(selected):
            if table.isRowHidden(k):
                continue

            J, zone = self.filter.zoneAt(k)

            if (J, zone) not in zones:
                zones.append((J, zone))

        for k, (J, zone) in enumerate(zones):
            dlg = ZoneAnalysis(zone, table)
            dlg.setWindowTitle(f"Analyzing Zone {J} "
                               f"({k+1} of {len(zones)} selected)...")

            if not dlg.exec_():
                break

        table.contentsModified.emit()

    def createDlg(self, table, index):
        J, zone = self.filter.zoneAt(index.data(Qt.UserRole))
        dlg = QLevels(table)
        dlg.setFilter(self.filter, True)
        dlg.setZone(zone)
        dlg.settingsApplied.connect(table.contentsModified)
        dlg.zoneChanged.connect(partial(self.scrollTableToZone, table))
        dlg.slider.slider.setValue(
            self.filter.cumulativeIndexMap[index.data(Qt.UserRole)])

        if dlg.exec_():
            tm = table.model()
            idx1 = tm.index(0, 0)
            idx2 = tm.index(self.rowCount()-1, self.columnCount()-1)
            tm.dataChanged.emit(idx1, idx2)
