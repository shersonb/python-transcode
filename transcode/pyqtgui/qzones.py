from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QColor, QFont, QBrush, QPen, QStandardItemModel, QIcon, QFontMetrics
from PyQt5.QtCore import Qt, QRegExp, QItemSelectionModel, QObject, QPoint
from PyQt5.QtWidgets import (QApplication, QItemDelegate, QLineEdit, QMenu, QAction, QAbstractItemView, QProgressDialog, QMessageBox,
                             QDialog, QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton, QSlider, QStyleOptionSlider, QStyle, QCheckBox,
                             QLabel, QWidget, QScrollBar, QGridLayout, QComboBox)
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtGui import QRegExpValidator
from fractions import Fraction as QQ
import regex
from functools import partial
from itertools import islice
from more_itertools import peekable
import numpy
from numpy import sqrt
import threading

from .slider import Slider
from .qimageview import QImageView
from ..filters.video.zoned import Zone, ZonedFilter
from ..filters.base import BaseFilter

from av import VideoFrame

class BaseShadowZone(object):
    def __init__(self, zone):
        self._zone = zone
        print(zone.prev)
        super().__init__(zone)
        self.__setstate__(zone.__getstate__())

    @property
    def src_start(self):
        return self._zone.src_start

    @property
    def src_end(self):
        return self._zone.src_end

    @property
    def prev_start(self):
        return self._zone.prev_start

    @property
    def prev_end(self):
        return self._zone.prev_end

    @property
    def dest_start(self):
        return self._zone.dest_start

    @property
    def dest_end(self):
        return self._zone.dest_end

    @property
    def prev(self):
        return self._zone.prev

    @prev.setter
    def prev(self, value):
        pass

    @property
    def next(self):
        return self._zone.next

    @next.setter
    def next(self, value):
        pass

    @property
    def parent(self):
        return self._zone.parent

    @parent.setter
    def parent(self, value):
        pass

class ZoneDlg(QDialog):
    sbfont = QFont("Dejavu Serif", 8)
    zonename = "Zone"
    title = "Zone Editor"
    shadowclass = BaseShadowZone
    zoneChanged = pyqtSignal(Zone)
    settingsApplied = pyqtSignal()

    def __init__(self, zone=None, *args, **kwargs):
        super(ZoneDlg, self).__init__(*args, **kwargs)
        self.setWindowTitle(self.title)
        self.zone = zone

        self.toggleZoneAct = QAction("&Toggle", self, shortcut="Ctrl+T",
                triggered=self.toggleZone)

        self.addAction(self.toggleZoneAct)

        self._mode = 2

        self._prepare()

        if zone is not None:
            self.loadZone(zone)

    def _prepare(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        self._prepareImageView()
        self._prepareStdZoneControls()
        self._prepareDlgButtons()

    def _prepareImageView(self, layout=None, index=None):
        if layout is None:
            layout = self.layout()

        self.imageView = QImageView(self)

        if self.zone.parent is not None:
            self.imageView.setFrame(QPixmap(self.zone.parent.width, self.zone.parent.height))
            self.imageView.setSar(self.zone.parent.sar)

        if isinstance(layout, QGridLayout):
            layout.addWidget(self.imageView, *index)

        elif isinstance(layout, QScrollArea):
            layout.setWidget(self.imageView)

        elif index is not None:
            layout.insertWidget(index, self.imageView)

        else:
            layout.addWidget(self.imageView)

    def _prepareStdZoneControls(self, layout=None, index=None):
        if layout is None:
            layout = self.layout()

        self.prevBtn = QPushButton(self)
        self.prevBtn.setToolTip(f"Previous {self.zonename}")
        self.prevBtn.setIcon(QIcon.fromTheme("go-previous"))
        self.prevBtn.clicked.connect(self.prevZone)

        self.slider = Slider(self)
        self.slider.setOrientation(Qt.Horizontal)
        self.slider.valueChanged.connect(self.loadFrame)
        self.slider.setTickInterval(1)

        self.nextBtn = QPushButton(self)
        self.nextBtn.setToolTip(f"Next {self.zonename}")
        self.nextBtn.setIcon(QIcon.fromTheme("go-next"))
        self.nextBtn.clicked.connect(self.nextZone)

        self.startLabel = QLabel(self)
        self.currentLabel = QLabel(self)
        self.endLabel = QLabel(self)

        self._createModeBox()
        self.modeBox.currentIndexChanged.connect(self.setMode)
        self.toggleZoneBtn = QPushButton(f"&Insert {self.zonename} Here", self)
        self.toggleZoneBtn.clicked.connect(self.toggleZone) # 162523

        sublayout1 = QHBoxLayout()
        sublayout1.addWidget(self.prevBtn)
        sublayout1.addWidget(self.slider)
        sublayout1.addWidget(self.nextBtn)

        sublayout2 = QHBoxLayout()
        sublayout2.addWidget(self.startLabel)
        sublayout2.addStretch()
        sublayout2.addWidget(self.currentLabel)
        sublayout2.addStretch()
        sublayout2.addWidget(self.endLabel)

        sublayout3 = QHBoxLayout()

        if len(self.modeBox) > 1:
            sublayout3.addWidget(self.modeBox)

        else:
            self.modeBox.setHidden(True)

        sublayout3.addWidget(self.toggleZoneBtn)

        if isinstance(layout, QGridLayout):
            suplayout = QVBoxLayout()
            suplayout.addLayout(sublayout1)
            suplayout.addLayout(sublayout2)
            suplayout.addLayout(sublayout3)
            layout.addLayout(suplayout, *index)

        elif index is not None:
            layout.insertLayout(index, sublayout1)
            layout.insertLayout(index+1, sublayout2)
            layout.insertLayout(index+2, sublayout3)

        else:
            layout.addLayout(sublayout1)
            layout.addLayout(sublayout2)
            layout.addLayout(sublayout3)

    def _createModeBox(self):
        self.modeBox = comboBox = QComboBox(self)
        comboBox.addItem("Original", 0)
        comboBox.addItem("Input", 1)
        comboBox.addItem("Output", 2)
        comboBox.setCurrentIndex(2)

    def setMode(self, mode):
        m = n = self.slider.value()
        self.slider.blockSignals(True)

        if self.zone:
            if self._mode == 0:
                if self.modeBox.currentData() == 1:
                    if isinstance(self.zone.parent.prev, BaseFilter):
                        if n > 0:
                            m = self.zone.parent.prev.cumulativeIndexMap[n-1] + 1

                        else:
                            m = self.zone.parent.prev.cumulativeIndexMap[n]

                    else:
                        m = n

                if self.modeBox.currentData() == 2:
                    if n > 0:
                        m = self.zone.parent.cumulativeIndexMap[n-1] + 1

                    else:
                        m = self.zone.parent.cumulativeIndexMap[n]

            elif self._mode == 1:
                if self.modeBox.currentData() == 0:
                    if isinstance(self.zone.parent.prev, BaseFilter):
                        if n > 0:
                            m = self.zone.parent.prev.cumulativeIndexReverseMap[n-1] + 1

                        else:
                            m = self.zone.parent.prev.cumulativeIndexReverseMap[n]

                    else:
                        m = n

                if self.modeBox.currentData() == 2:
                    if n > 0:
                        m = self.zone.parent.indexMap[n-1] + 1

                    else:
                        m = self.zone.parent.indexMap[n]

            elif self._mode == 2:
                if self.modeBox.currentData() == 0:
                    if isinstance(self.zone.parent.prev, BaseFilter):
                        if n > 0:
                            m = self.zone.parent.cumulativeIndexReverseMap[n-1] + 1

                        else:
                            m = self.zone.parent.cumulativeIndexReverseMap[n]

                    else:
                        m = n

                if self.modeBox.currentData() == 1:
                    if n > 0:
                        m = self.zone.parent.reverseIndexMap[n-1] + 1

                    else:
                        m = self.zone.parent.reverseIndexMap[n]


        self._mode = self.modeBox.currentData()
        self._updateSliderInterval()
        self.slider.setValue(m)
        self.slider.blockSignals(False)
        self.loadFrame(m)

    def _prepareDlgButtons(self, layout=None, index=None, layoutcls=QHBoxLayout):
        if layout is None:
            layout = self.layout()

        self.okayBtn = QPushButton("&Okay", self)
        self.okayBtn.setDefault(True)
        self.okayBtn.clicked.connect(self.applyAndClose)

        self.applyBtn = QPushButton("&Apply", self)
        self.applyBtn.clicked.connect(self.apply)

        self.resetBtn = QPushButton("&Reset", self)
        self.resetBtn.clicked.connect(self.reset)

        self.closeBtn = QPushButton("&Close", self)
        self.closeBtn.clicked.connect(self.close)

        sublayout = layoutcls()
        sublayout.addStretch()
        sublayout.addWidget(self.okayBtn)
        sublayout.addWidget(self.applyBtn)
        sublayout.addWidget(self.resetBtn)
        sublayout.addWidget(self.closeBtn)

        if isinstance(layout, QGridLayout):
            layout.addLayout(sublayout, *index)

        elif index is not None:
            layout.insertLayout(index, sublayout)

        else:
            layout.addLayout(sublayout)

    def _updateSliderInterval(self):
        self.slider.blockSignals(True)

        if self._mode == 0:
            self.slider.setMinimum(self.zone.src_start)
            self.slider.setMaximum(self.zone.src_end - 1)
            n1 = self.zone.src_start
            n2 = self.zone.src_end
            startpts = self.zone.parent.src.pts_time[n1]
            endpts = self.zone.parent.src.pts_time[n2 - 1]

        if self._mode == 1:
            self.slider.setMinimum(self.zone.prev_start)
            self.slider.setMaximum(self.zone.prev_end - 1)
            n1 = self.zone.prev_start
            n2 = self.zone.prev_end
            startpts = self.zone.parent.prev.pts_time[n1]
            endpts = self.zone.parent.prev.pts_time[n2 - 1]

        if self._mode == 2:
            self.slider.setMinimum(self.zone.dest_start)
            self.slider.setMaximum(self.zone.dest_end - 1)
            n1 = self.shadow.dest_start
            n2 = self.shadow.dest_end
            startpts = self.shadow.pts_time[0]
            endpts = self.shadow.pts_time[-1]

        self.slider.blockSignals(False)

        framecount = n2 - n1 + 1

        if framecount == 0:
            self.startLabel.setText("—")
            self.endLabel.setText("—")

        else:
            m, s = divmod(startpts, 60)
            m = int(m)
            h, m = divmod(m, 60)
            self.startLabel.setText(f"{n1} ({h:.0f}:{m:02.0f}:{s:06.3f})")

            m, s = divmod(endpts, 60)
            m = int(m)
            h, m = divmod(m, 60)
            self.endLabel.setText(f"{n2 - 1} ({h:.0f}:{m:02.0f}:{s:06.3f})")

    def loadZone(self, zone):
        self.zone = zone
        self.shadow = self.shadowclass(zone)
        self._updateSliderInterval()
        self.slider.setValue(self.slider.minimum())
        self.prevBtn.setDisabled(zone.prev is None)
        self.nextBtn.setDisabled(zone.next is None)
        self.loadFrame(self.slider.minimum())
        self._loadZone()
        self.notModified()
        self.zoneChanged.emit(zone)

    def _loadZone(self):
        pass

    @pyqtSlot()
    def toggleZone(self):
        n = self.slider.value()

        if self._mode == 0:
            if n > self.zone.src_start:
                J, zone = self.zone.parent.insertZoneAt(int(n))
                self.loadZone(zone)

            else:
                prevzone = self.zone.prev
                self.zone.parent.removeZoneAt(self.zone.src_start)
                self.loadZone(prevzone)
                self.slider.setValue(n)


        elif self._mode == 1:
            if n > self.zone.prev_start:
                if isinstance(self.zone.parent.prev, BaseFilter):
                    if n > 0:
                        m = self.zone.parent.prev.cumulativeIndexReverseMap[n-1] + 1

                    else:
                        m = self.zone.parent.prev.cumulativeIndexReverseMap[n]

                else:
                    m = n

                J, zone = self.zone.parent.insertZoneAt(int(m))
                self.loadZone(zone)

            else:
                prevzone = self.zone.prev
                self.zone.parent.removeZoneAt(self.zone.src_start)
                self.loadZone(prevzone)
                self.slider.setValue(n)

        elif self._mode == 2:
            if n > self.zone.dest_start:
                if n > 0:
                    m = self.zone.parent.cumulativeIndexReverseMap[n-1] + 1

                else:
                    m = self.zone.parent.cumulativeIndexReverseMap[n]

                J, zone = self.zone.parent.insertZoneAt(int(m))
                self.loadZone(zone)

            else:
                prevzone = self.zone.prev
                self.zone.parent.removeZoneAt(self.zone.src_start)
                self.loadZone(prevzone)
                self.slider.setValue(n)

    @pyqtSlot()
    def prevZone(self):
        self.loadZone(self.zone.prev)

    @pyqtSlot()
    def nextZone(self):
        self.loadZone(self.zone.next)

    @pyqtSlot()
    def loadFrame(self, n=None):
        if n is None:
            n = self.slider.value()

        if self._mode == 0:
            if isinstance(self.zone.parent.src, BaseFilter):
                frame = next(self.zone.parent.src.iterFrames(n))

            else:
                frame = next(self.zone.parent.src.iterFrames(n, whence="framenumber"))

            pts = self.zone.parent.src.pts_time[n]

            if n > self.zone.src_start:
                self.toggleZoneBtn.setText(f"&Insert {self.zonename} Here")

            else:
                self.toggleZoneBtn.setText(f"&Remove {self.zonename} Here")

        elif self._mode == 1:
            if isinstance(self.zone.parent.prev, BaseFilter):
                frame = next(self.zone.parent.prev.iterFrames(n))

            else:
                frame = next(self.zone.parent.prev.iterFrames(n, whence="framenumber"))

            pts = self.zone.parent.prev.pts_time[n]

            if n > self.zone.prev_start:
                self.toggleZoneBtn.setText(f"&Insert {self.zonename} Here")

            else:
                self.toggleZoneBtn.setText(f"&Remove {self.zonename} Here")

        elif self._mode == 2:
            frame = self.generatePreview(n)
            pts = self.shadow.pts_time[n - self.shadow.dest_start]

            if n > self.shadow.dest_start:
                self.toggleZoneBtn.setText(f"&Insert {self.zonename} Here")

            else:
                self.toggleZoneBtn.setText(f"&Remove {self.zonename} Here")

        im = frame.to_image()
        imw, imh = im.size
        zlevel = min((1, 1800/imw, 720/imh))
        self.imageView.setFrame(im.toqpixmap())

        self.toggleZoneBtn.setEnabled(n > 0)

        try:
            m, s = divmod(pts, 60)
            m = int(m)
            h, m = divmod(m, 60)
            self.currentLabel.setText(f"{n} ({h:.0f}:{m:02.0f}:{s:06.3f})")

        except IndexError:
            self.currentLabel.setText(f"{n} (-:--:--.---)")


    def generatePreview(self, n):
        start = self.shadow.getIterStart(n)
        frames = peekable(self.shadow.parent.prev.iterFrames(start, whence="framenumber"))

        prev_start = self.shadow.parent.prev.frameIndexFromPts(frames.peek().pts)
        framecount = self.shadow.prev_end - prev_start

        for frame in self.shadow.processFrames(islice(frames, int(framecount)), prev_start):
            if frame.pts >= self.shadow.pts[n - self.shadow.dest_start]:
                return frame

        return VideoFrame(width=self.shadow.parent.width, height=self.shadow.parent.height)

    @pyqtSlot()
    def show(self):
        if self.parent() is not None:
            self.parent().setDisabled(True)

        QDialog.show(self)

    @pyqtSlot()
    def applyAndClose(self):
        self.apply()
        self.close()

    @pyqtSlot()
    def apply(self):
        self.zone.__setstate__(self.shadow.__getstate__())
        self.settingsApplied.emit()
        self.notModified()

    @pyqtSlot()
    def reset(self):
        self.shadow.__setstate__(self.zone.__getstate__())
        self._loadZone()
        self.notModified()

    @pyqtSlot()
    def close(self):
        if self.parent() is not None:
            self.parent().setEnabled(True)

        QDialog.close(self)

    def isModified(self):
        self.modified = True

        if hasattr(self, "closeBtn") and self.closeBtn is not None:
            self.closeBtn.setText("&Cancel")

        if hasattr(self, "okayBtn") and self.okayBtn is not None:
            self.okayBtn.setDisabled(False)

        if hasattr(self, "resetBtn") and self.resetBtn is not None:
            self.resetBtn.setDisabled(False)

        if hasattr(self, "applyBtn") and self.applyBtn is not None:
            self.applyBtn.setDisabled(False)

    def notModified(self):
        self.modified = False

        if hasattr(self, "closeBtn") and self.closeBtn is not None:
            self.closeBtn.setText("&Close")

        if hasattr(self, "okayBtn") and self.okayBtn is not None:
            self.okayBtn.setDisabled(True)

        if hasattr(self, "resetBtn") and self.resetBtn is not None:
            self.resetBtn.setDisabled(True)

        if hasattr(self, "applyBtn") and self.applyBtn is not None:
            self.applyBtn.setDisabled(True)
