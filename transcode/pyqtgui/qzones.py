from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import QTime, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (QAction, QDialog, QVBoxLayout, QHBoxLayout, QScrollArea,
                             QPushButton, QLabel, QWidget, QGridLayout, QComboBox, QMessageBox)

from itertools import islice
from more_itertools import peekable
from numpy import concatenate

from .qframeselect import QFrameSelect
from .qimageview import QImageView
from .qfilterconfig import QFilterConfig
from ..filters.video.zoned import Zone
from ..filters.base import BaseFilter

from av import VideoFrame


class BaseShadowZone(object):
    def __init__(self, zone):
        self._zone = zone
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


class ZoneDlg(QFilterConfig):
    zonename = "Zone"
    zoneChanged = pyqtSignal(Zone)
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        self.shadow = None
        self.shadowzone = None
        self._mode = 2
        super().__init__(*args, **kwargs)
        self.toggleZoneAct = QAction("&Toggle", self, shortcut="Ctrl+T",
                                     triggered=self.toggleZone)

        self.addAction(self.toggleZoneAct)

    def _createControls(self):
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

        self._createImageView()
        self._createZoneNavControls()
        self._createZoneControls()
        self._createZoneButtons()
        self._createGlobalControls()
        self._createDlgButtons()

    def _prevChanged(self, source):
        if source is None:
            self.slider.setPtsTimeArray(None)

        else:
            self.slider.setPtsTimeArray(source.pts_time)
            self.loadFrame(self.slider.slider.value(),
                           self.slider.currentTime.time())

    def _createImageView(self, layout=None, index=None):
        if layout is None:
            layout = self.layout()

        self.imageView = QImageView(self)

        if isinstance(layout, QGridLayout):
            layout.addWidget(self.imageView, *index)

        elif isinstance(layout, QScrollArea):
            layout.setWidget(self.imageView)

        elif index is not None:
            layout.insertWidget(index, self.imageView)

        else:
            layout.addWidget(self.imageView)

    def _createZoneNavControls(self, layout=None, index=None):
        if layout is None:
            layout = self.layout()

        self.prevBtn = QPushButton(self)
        self.prevBtn.setToolTip(f"Previous {self.zonename}")
        self.prevBtn.setIcon(QIcon.fromTheme("go-previous"))
        self.prevBtn.clicked.connect(self.prevZone)

        self.slider = QFrameSelect(self)
        self.slider.setStartEndVisible(True)
        self.slider.frameSelectionChanged.connect(self.loadFrame)

        self.nextBtn = QPushButton(self)
        self.nextBtn.setToolTip(f"Next {self.zonename}")
        self.nextBtn.setIcon(QIcon.fromTheme("go-next"))
        self.nextBtn.clicked.connect(self.nextZone)

        self._createModeBox()
        self.modeBox.currentIndexChanged.connect(self.setMode)
        self.toggleZoneBtn = QPushButton(f"&Insert {self.zonename} Here", self)
        self.toggleZoneBtn.clicked.connect(self.toggleZone)  # 162523

        sublayout1 = QHBoxLayout()
        sublayout1.addWidget(self.prevBtn)
        sublayout1.addWidget(self.slider)
        sublayout1.addWidget(self.nextBtn)

        sublayout3 = QHBoxLayout()

        if len(self.modeBox) > 1:
            sublayout3.addWidget(self.modeBox)

        else:
            self.modeBox.setHidden(True)

        sublayout3.addWidget(self.toggleZoneBtn)

        if isinstance(layout, QGridLayout):
            suplayout = QVBoxLayout()
            suplayout.addLayout(sublayout1)
            suplayout.addLayout(sublayout3)
            layout.addLayout(suplayout, *index)

        elif index is not None:
            layout.insertLayout(index, sublayout1)
            layout.insertLayout(index+1, sublayout3)

        else:
            layout.addLayout(sublayout1)
            layout.addLayout(sublayout3)

    def _createModeBox(self):
        self.modeBox = comboBox = QComboBox(self)
        comboBox.addItem("Original", 0)
        comboBox.addItem("Input", 1)
        comboBox.addItem("Output", 2)
        comboBox.setCurrentIndex(2)

    def _createZoneControls(self, layout=None, index=None):
        pass

    def _createZoneButtons(self, layout=None, index=None, layoutcls=QHBoxLayout):
        self.applyZoneBtn = QPushButton("Apply Zone Settings", self)
        self.resetZoneBtn = QPushButton("Reset Zone Settings", self)

        self.applyZoneBtn.clicked.connect(self.applyZone)
        self.resetZoneBtn.clicked.connect(self.resetZone)

        if layout is None:
            layout = self.layout()

        sublayout = layoutcls()
        sublayout.addStretch()
        sublayout.addWidget(self.applyZoneBtn)
        sublayout.addWidget(self.resetZoneBtn)

        if isinstance(layout, QGridLayout):
            layout.addLayout(sublayout, *index)

        elif index is not None:
            layout.insertLayout(index, sublayout)

        else:
            layout.addLayout(sublayout)

    def _resetControls(self):
        self.setZone(self.shadow[0])
        self._resetGlobalControls()

    def setMode(self, mode):
        m = n = self.slider.slider.value()

        if self.zone:
            if self._mode == 0:
                if self.modeBox.currentData() == 1:
                    if isinstance(self.shadow.prev, BaseFilter):
                        idxmap = self.shadow.prev.cumulativeIndexMap

                    else:
                        idxmap = None

                if self.modeBox.currentData() == 2:
                    idxmap = self.shadow.cumulativeIndexMap

            elif self._mode == 1:
                if self.modeBox.currentData() == 0:
                    if isinstance(self.shadow.prev, BaseFilter):
                        idxmap = self.shadow.prev.cumulativeIndexReverseMap

                    else:
                        idxmap = None

                if self.modeBox.currentData() == 2:
                    idxmap = self.shadow.indexMap

            elif self._mode == 2:
                if self.modeBox.currentData() == 0:
                    if isinstance(self.shadow, BaseFilter):
                        idxmap = self.shadow.cumulativeIndexReverseMap

                    else:
                        idxmap = None

                if self.modeBox.currentData() == 1:
                    idxmap = self.shadow.reverseIndexMap

        if idxmap is None:
            m = n

        elif n > 0:
            m = idxmap[n-1] + 1

        else:
            m = idxmap[n]

        self._mode = self.modeBox.currentData()
        self._updateSliderInterval()
        self.slider.slider.setValue(m)
        self.loadFrame(m, QTime())

    def _createGlobalControls(self, layout=None, index=None):
        pass

    def _createDlgButtons(self, layout=None, index=None, layoutcls=QHBoxLayout):
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
            self.slider.setPtsTimeArray(self.shadow.source.pts_time)
            self.slider.setMinimum(self.shadowzone.src_start)
            self.slider.setMaximum(self.shadowzone.src_end - 1)

        if self._mode == 1:
            self.slider.setPtsTimeArray(self.shadow.prev.pts_time)
            self.slider.setMinimum(self.shadowzone.prev_start)
            self.slider.setMaximum(self.shadowzone.prev_end - 1)

        if self._mode == 2:
            pts_time = self.shadow.pts_time

            if self.shadowzone is not None:
                pts_time = concatenate((
                    pts_time[:self.shadowzone.dest_start],
                    self.shadowzone.pts_time,
                    pts_time[self.shadowzone.dest_end:]
                ))

            self.slider.setPtsTimeArray(pts_time)
            self.slider.setMinimum(self.shadowzone.dest_start)
            self.slider.setMaximum(self.shadowzone.dest_end - 1)

        self.slider.blockSignals(False)

    def setZone(self, zone):
        self.zone = zone

        if zone is not None:
            self.shadowzone = zone.copy()

            if self.shadow.prev is not None:
                self._updateSliderInterval()
                self.slider.slider.setValue(self.slider.slider.minimum())
                self.loadFrame(
                    self.slider.slider.minimum(),
                    self.slider.currentTime.minimumTime()
                )

            self.prevBtn.setDisabled(zone.prev is None)
            self.nextBtn.setDisabled(zone.next is None)

            self._resetZoneControls()
            self.zoneNotModified()
            self.zoneChanged.emit(zone)

        else:
            self.prevBtn.setDisabled(True)
            self.nextBtn.setDisabled(True)

    def _resetZoneControls(self):
        pass

    def _resetGlobalControls(self):
        pass

    @pyqtSlot()
    def toggleZone(self):
        n = self.slider.slider.value()
        newzone = (self._mode == 0 and n > self.shadowzone.src_start) or \
            (self._mode == 1 and n > self.shadowzone.prev_start) or \
            (self._mode == 2 and n > self.shadowzone.dest_start)

        if newzone and self.zonemodified:
            answer = self.askApplyZone()

            if answer == QMessageBox.Yes:
                self.applyZone()

            elif answer == QMessageBox.Cancel:
                return

        elif not newzone and self.askRemoveZone() == QMessageBox.No:
            return

        if self._mode == 0:
            if n > self.shadowzone.src_start:
                J, zone = self.shadow.insertZoneAt(int(n))
                self.setZone(zone)

            else:
                prevzone = self.shadowzone.prev
                self.shadow.removeZoneAt(self.shadowzone.src_start)
                self.setZone(prevzone)
                self.slider.slider.setValue(n)

        elif self._mode == 1:
            if n > self.zone.prev_start:
                if isinstance(self.shadow.prev, BaseFilter):
                    if n > 0:
                        m = self.shadow.prev.cumulativeIndexReverseMap[n-1] + 1

                    else:
                        m = self.shadow.prev.cumulativeIndexReverseMap[n]

                else:
                    m = n

                J, zone = self.shadow.insertZoneAt(int(m))
                self.setZone(zone)

            else:
                prevzone = self.zone.prev
                self.shadow.removeZoneAt(self.shadowzone.src_start)
                self.setZone(prevzone)
                self.slider.setValue(n)

        elif self._mode == 2:
            if n > self.zone.dest_start:
                if n > 0:
                    m = self.shadow.cumulativeIndexReverseMap[n-1] + 1

                else:
                    m = self.shadow.cumulativeIndexReverseMap[n]

                J, zone = self.shadow.insertZoneAt(int(m))
                self.setZone(zone)

            else:
                prevzone = self.zone.prev
                self.shadow.removeZoneAt(self.shadowzone.src_start)
                self.setZone(prevzone)
                self.slider.setValue(n)

        self.isModified()

    @pyqtSlot()
    def prevZone(self):
        if self.zonemodified:
            answer = self.askApplyZone()

            if answer == QMessageBox.Yes:
                self.applyZone()

            elif answer == QMessageBox.Cancel:
                return

        self.setZone(self.zone.prev)

    @pyqtSlot()
    def nextZone(self):
        if self.zonemodified:
            answer = self.askApplyZone()

            if answer == QMessageBox.Yes:
                self.applyZone()

            elif answer == QMessageBox.Cancel:
                return

        self.setZone(self.zone.next)

    @pyqtSlot(int, QTime)
    def loadFrame(self, n, t):
        if n is None:
            n = self.slider.slider.value()

        if self._mode == 0:
            frame = next(self.shadow.source.iterFrames(
                n, whence="framenumber"))

            if n > self.shadowzone.src_start:
                self.toggleZoneBtn.setText(f"&Insert {self.zonename} Here")

            else:
                self.toggleZoneBtn.setText(f"&Remove {self.zonename} Here")

        elif self._mode == 1:
            frame = next(self.shadow.prev.iterFrames(n, whence="framenumber"))

            if n > self.zone.prev_start:
                self.toggleZoneBtn.setText(f"&Insert {self.zonename} Here")

            else:
                self.toggleZoneBtn.setText(f"&Remove {self.zonename} Here")

        elif self._mode == 2:
            frame = self.generatePreview(n)

            if n > self.shadowzone.dest_start:
                self.toggleZoneBtn.setText(f"&Insert {self.zonename} Here")

            else:
                self.toggleZoneBtn.setText(f"&Remove {self.zonename} Here")

        im = frame.to_rgb().to_image()
        pixmap = im.toqpixmap()
        self.imageView.setFrame(pixmap)

        self.toggleZoneBtn.setEnabled(n > 0)

    def generatePreview(self, n):
        try:
            return next(self.shadowzone.iterFrames(n))

        except StopIteration:
            return VideoFrame(width=self.shadow.width, height=self.shadow.height)

    @pyqtSlot()
    def applyZone(self):
        self.zone.__setstate__(self.shadowzone.__getstate__())
        self.zoneNotModified()
        self.isModified()

    @pyqtSlot()
    def resetZone(self):
        self.shadowzone.__setstate__(self.filter.__getstate__())
        self._resetZoneControls()
        self.zoneNotModified()

    def zoneModified(self):
        self.zonemodified = True

        if hasattr(self, "applyZoneBtn") and self.applyZoneBtn is not None:
            self.applyZoneBtn.setDisabled(False)

        if hasattr(self, "resetZoneBtn") and self.resetZoneBtn is not None:
            self.resetZoneBtn.setDisabled(False)

        if self.filter is not self.shadow:
            self.isModified()

    def zoneNotModified(self):
        self.zonemodified = False

        if hasattr(self, "applyZoneBtn") and self.applyZoneBtn is not None:
            self.applyZoneBtn.setDisabled(True)

        if hasattr(self, "resetZoneBtn") and self.resetZoneBtn is not None:
            self.resetZoneBtn.setDisabled(True)

    def apply(self):
        if self.zonemodified:
            answer = self.askApplyZone()

            if answer == QMessageBox.Yes:
                self.applyZone()

            elif answer == QMessageBox.Cancel:
                return

        super().apply()

    def closeEvent(self, event):
        if self.zonemodified and not self.modified:
            answer = self.askApplyZone()

            if answer == QMessageBox.Yes:
                self.applyZone()

            elif answer == QMessageBox.Cancel:
                event.ignore()
                return

        super().closeEvent(event)

    def askApplyZone(self):
        return QMessageBox.question(self, "Apply zone settings?",
                                    "Do you wish to apply zone settings?",
                                    QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)

    def askRemoveZone(self):
        return QMessageBox.question(self, "Remove?",
                                    "Are you sure you wish to remove zone?",
                                    QMessageBox.Yes | QMessageBox.No)

