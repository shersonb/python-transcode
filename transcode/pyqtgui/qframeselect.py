from PyQt5.QtCore import QTime, pyqtSignal, Qt
from PyQt5.QtWidgets import (
    QWidget, QTimeEdit, QLabel, QSpinBox, QVBoxLayout, QHBoxLayout)
from .slider import Slider
from transcode.util import search


class QFrameSelect(QWidget):
    frameSelectionChanged = pyqtSignal(int, QTime)

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

        self.currentTime = QTimeEdit(self)
        self.currentTime.setDisplayFormat("H:mm:ss.zzz")
        self.currentTime.timeChanged.connect(self._handleTimeEditChange)
        self.currentTime.editingFinished.connect(self._handleTimeEditFinished)

        self.rightLabel = QLabel(self)

        hlayout.addWidget(self.leftLabel)
        hlayout.addStretch()
        hlayout.addWidget(QLabel("Frame index:", self))
        hlayout.addWidget(self.spinBox)
        hlayout.addWidget(QLabel("Timestamp:", self))
        hlayout.addWidget(self.currentTime)
        hlayout.addStretch()
        hlayout.addWidget(self.rightLabel)

        self.setPtsTimeArray(None)

    def setValue(self, n):
        self.slider.setValue(n)

    def setMinimum(self, n=0):
        self.slider.setMinimum(n)
        self.spinBox.setMinimum(n)

        ms = int(self.pts_time[n]*1000 + 0.5)
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)

        self.currentTime.setMinimumTime(QTime(h, m, s, ms))
        self.leftLabel.setText(f"{n} ({h}:{m:02d}:{s:02d}.{ms:03d})")

    def setMaximum(self, n=None):
        if n is None:
            n = len(self.pts_time) - 1

        self.slider.setMaximum(n)
        self.spinBox.setMaximum(n)

        ms = int(self.pts_time[n]*1000 + 0.5)
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)

        self.currentTime.setMaximumTime(QTime(h, m, s, ms))
        self.rightLabel.setText(f"{n} ({h}:{m:02d}:{s:02d}.{ms:03d})")

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
            self.currentTime.setDisabled(False)

        else:
            self.slider.setMinimum(0)
            self.slider.setMaximum(0)
            self.slider.setSnapValues(None)
            self.slider.setDisabled(True)
            self.spinBox.setDisabled(True)
            self.currentTime.setDisabled(True)

    def _handleSliderChange(self, n):
        self.spinBox.blockSignals(True)
        self.spinBox.setValue(n)
        self.spinBox.blockSignals(False)

        pts_time = self.pts_time[n]
        ms = int(pts_time*1000 + 0.5)
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)

        self.currentTime.blockSignals(True)
        self.currentTime.setTime(QTime(h, m, s, ms))
        self.currentTime.blockSignals(False)

        self.frameSelectionChanged.emit(n, QTime(h, m, s, ms))

    def _handleSpinboxChange(self, n):
        self.slider.blockSignals(True)
        self.slider.setValue(n)
        self.slider.blockSignals(False)

        pts_time = self.pts_time[n]
        ms = int(pts_time*1000 + 0.5)
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)

        self.currentTime.blockSignals(True)
        self.currentTime.setTime(QTime(h, m, s, ms))
        self.currentTime.blockSignals(False)

        self.frameSelectionChanged.emit(n, QTime(h, m, s, ms))

    def _handleTimeEditChange(self, t):
        pts = t.msecsSinceStartOfDay()/1000

        try:
            n = search(self.pts_time, pts + 0.0005, dir="-")

        except IndexError:
            n = 0

        if n != self.slider.value():
            self.slider.blockSignals(True)
            self.slider.setValue(n)
            self.slider.blockSignals(False)

            self.spinBox.blockSignals(True)
            self.spinBox.setValue(n)
            self.spinBox.blockSignals(False)

            pts_time = self.pts_time[n]
            ms = int(pts_time*1000 + 0.5)
            s, ms = divmod(ms, 1000)
            m, s = divmod(s, 60)
            h, m = divmod(m, 60)

            self.frameSelectionChanged.emit(n, QTime(h, m, s, ms))

    def _handleTimeEditFinished(self):
        t = self.currentTime.time()
        pts = t.msecsSinceStartOfDay()/1000
        n = search(self.pts_time, pts + 0.0005, dir="-")
        pts_time = self.pts_time[n]

        ms = int(pts_time*1000 + 0.5)
        s, ms = divmod(ms, 1000)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        T = QTime(h, m, s, ms)

        if t != T:
            self.currentTime.setTime(T)
