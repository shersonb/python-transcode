#!/usr/bin/python
from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QLabel, QSpinBox, QVBoxLayout, QHBoxLayout, QWidget)

import numpy
from numpy import sqrt, concatenate

from . import Slice
from transcode.util import search
from transcode.pyqtgui.slider import Slider
from transcode.pyqtgui.qimageview import QImageView
from transcode.pyqtgui.qfilterconfig import QFilterConfig
from transcode.pyqtgui.qtimeselect import QTimeSelect


class QTimeSlider(QWidget):
    """
    This will be slightly different from QTimeSelect in that time down
    to the nearest nanosecond can be selected, and need not be snapped to
    the nearest video frame.
    """
    timeSelectionChanged = pyqtSignal(int, float)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.slider = Slider(self)
        self.slider.setOrientation(Qt.Horizontal)
        self.slider.valueChanged.connect(self._handleSliderChange)
        self.slider.setTickInterval(1)

        layout.addWidget(self.slider)

        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)

        self.leftLabel = QLabel(self)

        self.spinBox = QSpinBox(self)
        self.spinBox.valueChanged.connect(self._handleSpinboxChange)

        self.timeSelect = QTimeSelect(self)
        self.timeSelect.valueChanged.connect(self._handleTimeEditChange)
        # self.timeSelect.editingFinished.connect(self._handleTimeEditFinished)

        self.rightLabel = QLabel(self)

        hlayout.addWidget(self.leftLabel)
        hlayout.addStretch()
        hlayout.addWidget(QLabel("Frame index:", self))
        hlayout.addWidget(self.spinBox)
        hlayout.addWidget(QLabel("Timestamp:", self))
        hlayout.addWidget(self.timeSelect)
        hlayout.addStretch()
        hlayout.addWidget(self.rightLabel)

        self.setPtsTimeArray(None)

    def setMinimum(self, n=0, t=None):
        self.slider.setMinimum(n)
        self.spinBox.setMinimum(n)

        if t is None:
            t = self.pts_time[n]

        self.timeSelect.setMinimum(t)

        m, s = divmod(self.pts_time[n], 60)
        h, m = divmod(int(m), 60)

        self.leftLabel.setText(f"{n} ({h}:{m:02d}:{s:012.9f})")

    def setMaximum(self, n=None, t=None):
        if n is None:
            n = len(self.pts_time) - 1

        self.slider.setMaximum(n)
        self.spinBox.setMaximum(n)

        if t is None:
            t = self.pts_time[n]

        self.timeSelect.setMaximum(t)

        m, s = divmod(self.pts_time[n], 60)
        h, m = divmod(int(m), 60)

        self.rightLabel.setText(f"{n} ({h}:{m:02d}:{s:012.9f})")

    def setStartEndVisible(self, value):
        self.leftLabel.setHidden(not bool(value))
        self.rightLabel.setHidden(not bool(value))

    def setPtsTimeArray(self, pts_time=None):
        self.pts_time = pts_time

        if pts_time is not None:
            N = len(pts_time)
            self.setMinimum(0)
            self.setMaximum(N - 1)

            self.slider.setValue(0)
            self.slider.setSnapValues(None)

            self.slider.setDisabled(False)
            self.spinBox.setDisabled(False)
            self.timeSelect.setDisabled(False)

        else:
            self.slider.setSnapValues(None)
            self.slider.setDisabled(True)
            self.spinBox.setDisabled(True)
            self.timeSelect.setDisabled(True)

    def _handleSliderChange(self, n):
        self.spinBox.blockSignals(True)
        self.spinBox.setValue(n)
        self.spinBox.blockSignals(False)

        if self.pts_time is None:
            self.timeSelectionChanged.emit(n, 0)
            return

        pts_time = self.pts_time[n]

        self.timeSelect.blockSignals(True)
        self.timeSelect.setValue(pts_time)
        self.timeSelect.blockSignals(False)

        self.timeSelectionChanged.emit(n, pts_time)

    def _handleSpinboxChange(self, n):
        self.slider.blockSignals(True)
        self.slider.setValue(n)
        self.slider.blockSignals(False)

        if self.pts_time is None:
            self.timeSelectionChanged.emit(n, 0)
            return

        pts_time = self.pts_time[n]

        self.timeSelect.blockSignals(True)
        self.timeSelect.setValue(pts_time)
        self.timeSelect.blockSignals(False)

        self.timeSelectionChanged.emit(n, pts_time)

    def _handleTimeEditChange(self, t):
        if self.pts_time is None:
            self.timeSelectionChanged.emit(0, t)
            return

        if t + 0.0005 >= self.pts_time[0]:
            n = search(self.pts_time, t + 0.0005, dir="-")

        else:
            n = 0

        if n != self.slider.value():
            self.slider.blockSignals(True)
            self.slider.setValue(n)
            self.slider.blockSignals(False)

            self.spinBox.blockSignals(True)
            self.spinBox.setValue(n)
            self.spinBox.blockSignals(False)

        self.timeSelectionChanged.emit(n, t)

    # def _handleTimeEditFinished(self):
        #t = self.timeSelect.time()
        #pts = t.msecsSinceStartOfDay()/1000
        #n = search(self.pts_time, pts, dir="-")
        #pts_time = self.pts_time[n]

        #ms = int(pts_time*1000 + 0.5)
        #s, ms = divmod(ms, 1000)
        #m, s = divmod(s, 60)
        #h, m = divmod(m, 60)
        #T = QTime(h, m, s, ms)

        # if t != T:
            # self.timeSelect.setTime(T)


class QSlice(QFilterConfig):
    allowedtypes = ("video", "audio", "subtitle")

    def _createControls(self):
        self.setWindowTitle("Configure Slice")

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.sourceWidget = QWidget(self)
        self.sourceSelection = self.createSourceControl(self.sourceWidget)
        self.sourceSelection.currentDataChanged.connect(self.setFilterSource)

        srclayout = QHBoxLayout()
        srclayout.addWidget(QLabel("Source: ", self.sourceWidget))
        srclayout.addWidget(self.sourceSelection)

        self.sourceWidget.setLayout(srclayout)
        layout.addWidget(self.sourceWidget)

        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)

        vlayout = QVBoxLayout()
        hlayout.addLayout(vlayout)
        self.startImageView = QImageView(self)
        self.startSlider = QTimeSlider(self)
        self.startSlider.timeSelectionChanged.connect(self.setStart)
        vlayout.addWidget(self.startImageView)
        vlayout.addWidget(self.startSlider)

        vlayout = QVBoxLayout()
        hlayout.addLayout(vlayout)
        self.endImageView = QImageView(self)
        self.endSlider = QTimeSlider(self)
        self.endSlider.timeSelectionChanged.connect(self.setEnd)
        vlayout.addWidget(self.endImageView)
        vlayout.addWidget(self.endSlider)

        self._prepareDlgButtons()

    @pyqtSlot(int, float)
    def setStart(self, n, t):
        self.filtercopy.startpts = t
        self.updateStartImage()
        self.isModified()

    @pyqtSlot(int, float)
    def setEnd(self, n, t):
        if self.filtercopy.prev is not None:
            if abs(t - self.filtercopy.prev.duration) < 10**-9:
                self.filtercopy.endpts = None

            else:
                self.filtercopy.endpts = t

        else:
            self.filtercopy.endpts = t

        self.updateEndImage()
        self.isModified()

    def updateStartImage(self):
        if self.filtercopy.prev is not None and self.filtercopy.prev.type == "video":
            n = search(self.filtercopy.prev.pts_time,
                       self.filtercopy.startpts + 0.0005, "-")

            try:
                frame = next(self.filtercopy.prev.iterFrames(
                    n, whence="framenumber"))

            except StopIteration:
                self.startImageView.setFrame(
                    QPixmap(self.filtercopy.prev.width, self.filtercopy.prev.height))
                return

            im = frame.to_image()
            pixmap = im.toqpixmap()
            self.startImageView.setFrame(pixmap)

    def updateEndImage(self):
        if self.filtercopy.prev is not None and self.filtercopy.prev.type == "video":
            if self.filtercopy.endpts is not None:
                n = search(self.filtercopy.prev.pts_time,
                           self.filtercopy.endpts + 0.0005, "-")

                try:
                    frame = next(self.filtercopy.prev.iterFrames(
                        n, whence="framenumber"))

                except StopIteration:
                    self.endImageView.setFrame(
                        QPixmap(self.filtercopy.prev.width, self.filtercopy.prev.height))
                    return

                im = frame.to_image()
                pixmap = im.toqpixmap()
                self.endImageView.setFrame(pixmap)

            else:
                self.endImageView.setFrame(
                    QPixmap(self.filtercopy.prev.width, self.filtercopy.prev.height))

    def createNewFilterInstance(self):
        return Slice()

    def _prevChanged(self, source):
        self._resetControlMaximums()

        # if source.type == "video":
        #self.loadFrame(self.slider.slider.value(), self.slider.timeSelect.time())

        self.startSlider.spinBox.setVisible(source.type == "video")
        self.startSlider.slider.setVisible(source.type == "video")
        self.startImageView.setVisible(source.type == "video")

        self.endSlider.spinBox.setVisible(source.type == "video")
        self.endSlider.slider.setVisible(source.type == "video")
        self.endImageView.setVisible(source.type == "video")

    def _resetControlMaximums(self):
        if self.filtercopy.prev is not None:
            pts_time = concatenate(
                (self.filtercopy.prev.pts_time, [float(self.filtercopy.prev.duration)]))
            self.startSlider.blockSignals(True)
            self.startSlider.setPtsTimeArray(pts_time)
            self.startSlider.blockSignals(False)

            self.endSlider.blockSignals(True)
            self.endSlider.setPtsTimeArray(pts_time)
            self.endSlider.blockSignals(False)

            if self.filtercopy.prev.type == "subtitle":
                self.startSlider.timeSelect.setMinimum(0)
                self.endSlider.timeSelect.setMinimum(0)
                self.startSlider.timeSelect.setMaximum(24*3600)
                self.endSlider.timeSelect.setMaximum(24*3600)

    def _resetControls(self):
        if self.filtercopy is not None:
            self._resetControlMaximums()

            self.startSlider.blockSignals(True)
            self.startSlider.timeSelect.setValue(self.filtercopy.startpts)
            self.startSlider.blockSignals(False)

            self.endSlider.blockSignals(True)

            if self.filtercopy.endpts is not None:
                self.endSlider.timeSelect.setValue(self.filtercopy.endpts)

            elif self.filtercopy.prev is not None:
                if self.filtercopy.prev.type in ("video", "audio"):
                    self.endSlider.timeSelect.setValue(
                        float(self.filtercopy.prev.duration))

                else:
                    self.endSlider.timeSelect.setValue(24*3600)

            self.endSlider.blockSignals(False)

            self.updateStartImage()
            self.updateEndImage()

        else:
            self.startSlider.setPtsTimeArray(numpy.array([0]))
            self.endSlider.setPtsTimeArray(numpy.array([0]))
