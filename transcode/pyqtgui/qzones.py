from PyQt5.QtGui import QPixmap, QFont, QIcon
from PyQt5.QtCore import QTime, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (QAction, QDialog, QVBoxLayout, QHBoxLayout, QScrollArea,
                             QPushButton, QLabel, QWidget, QGridLayout, QComboBox)

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


class ZoneDlg(QDialog):
    sbfont = QFont("Dejavu Serif", 8)
    zonename = "Zone"
    title = "Zone Editor"
    shadowclass = BaseShadowZone
    zoneChanged = pyqtSignal(Zone)
    contentsModified = pyqtSignal()

    def __init__(self, zone=None, *args, **kwargs):
        super(ZoneDlg, self).__init__(*args, **kwargs)
        self.setWindowTitle(self.title)
        self.zone = zone

        self.toggleZoneAct = QAction("&Toggle", self, shortcut="Ctrl+T",
                                     triggered=self.toggleZone)

        self.addAction(self.toggleZoneAct)

        self._mode = 2

        self._create()

        if zone is not None:
            self.loadZone(zone)

    def _create(self):
        layout = QVBoxLayout()
        self.setLayout(layout)
        self._createImageView()
        self._createStdZoneControls()
        self._createDlgButtons()

    def _createImageView(self, layout=None, index=None):
        if layout is None:
            layout = self.layout()

        self.imageView = QImageView(self)

        if self.zone.parent is not None:
            self.imageView.setFrame(
                QPixmap(self.zone.parent.width, self.zone.parent.height))
            self.imageView.setSar(self.zone.parent.sar)

        if isinstance(layout, QGridLayout):
            layout.addWidget(self.imageView, *index)

        elif isinstance(layout, QScrollArea):
            layout.setWidget(self.imageView)

        elif index is not None:
            layout.insertWidget(index, self.imageView)

        else:
            layout.addWidget(self.imageView)

    def _createStdZoneControls(self, layout=None, index=None):
        if layout is None:
            layout = self.layout()

        self.prevBtn = QPushButton(self)
        self.prevBtn.setToolTip(f"Previous {self.zonename}")
        self.prevBtn.setIcon(QIcon.fromTheme("go-previous"))
        self.prevBtn.clicked.connect(self.prevZone)

        self.slider = QFrameSelect(self)
        self.slider.frameSelectionChanged.connect(self.loadFrame)

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
        self.toggleZoneBtn.clicked.connect(self.toggleZone)  # 162523

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
        m = n = self.slider.slider.value()
        self.slider.slider.blockSignals(True)

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
        self.slider.slider.setValue(m)
        self.slider.slider.blockSignals(False)
        self.loadFrame(m, QTime())

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
            self.slider.setPtsTimeArray(self.zone.parent.source.pts_time)
            self.slider.setMinimum(self.zone.source.start)
            self.slider.setMaximum(self.zone.source.end - 1)
            n1 = self.zone.source.start
            n2 = self.zone.source.end
            startpts = self.zone.parent.source.pts_time[n1]
            endpts = self.zone.parent.source.pts_time[n2 - 1]

        if self._mode == 1:
            self.slider.setPtsTimeArray(self.zone.parent.prev.pts_time)
            self.slider.setMinimum(self.zone.prev_start)
            self.slider.setMaximum(self.zone.prev_end - 1)
            n1 = self.zone.prev_start
            n2 = self.zone.prev_end
            startpts = self.zone.parent.prev.pts_time[n1]
            endpts = self.zone.parent.prev.pts_time[n2 - 1]

        if self._mode == 2:
            self.slider.setPtsTimeArray(self.zone.parent.pts_time)
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
        self.slider.slider.setValue(self.slider.slider.minimum())
        self.prevBtn.setDisabled(zone.prev is None)
        self.nextBtn.setDisabled(zone.next is None)
        self.loadFrame(self.slider.slider.minimum(),
                       self.slider.currentTime.minimumTime())
        self._loadZone()
        self.notModified()
        self.zoneChanged.emit(zone)

    def _loadZone(self):
        pass

    @pyqtSlot()
    def toggleZone(self):
        n = self.slider.value()

        if self._mode == 0:
            if n > self.zone.source.start:
                J, zone = self.zone.parent.insertZoneAt(int(n))
                self.loadZone(zone)

            else:
                prevzone = self.zone.prev
                self.zone.parent.removeZoneAt(self.zone.source.start)
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
                self.zone.parent.removeZoneAt(self.zone.source.start)
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
                self.zone.parent.removeZoneAt(self.zone.source.start)
                self.loadZone(prevzone)
                self.slider.setValue(n)

        self.contentsModified.emit()
        self.done(1)

    @pyqtSlot()
    def prevZone(self):
        self.loadZone(self.zone.prev)

    @pyqtSlot()
    def nextZone(self):
        self.loadZone(self.zone.next)

    @pyqtSlot(int, QTime)
    def loadFrame(self, n, t):
        if n is None:
            n = self.slider.slider.value()

        if self._mode == 0:
            if isinstance(self.zone.parent.source. BaseFilter):
                frame = next(self.zone.parent.source.iterFrames(n))

            else:
                frame = next(self.zone.parent.source.iterFrames(
                    n, whence="framenumber"))

            pts = self.zone.parent.source.pts_time[n]

            if n > self.zone.source.start:
                self.toggleZoneBtn.setText(f"&Insert {self.zonename} Here")

            else:
                self.toggleZoneBtn.setText(f"&Remove {self.zonename} Here")

        elif self._mode == 1:
            if isinstance(self.zone.parent.prev, BaseFilter):
                frame = next(self.zone.parent.prev.iterFrames(n))

            else:
                frame = next(self.zone.parent.prev.iterFrames(
                    n, whence="framenumber"))

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
        im.show()
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
        frames = peekable(self.shadow.parent.prev.iterFrames(
            start, whence="framenumber"))

        prev_start = self.shadow.parent.prev.frameIndexFromPts(
            frames.peek().pts)
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
        self.done(1)
        self.contentsModified.emit()
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
            print("*", source.pts_time)
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
                        # if n > 0:
                        #m = self.zone.parent.prev.cumulativeIndexMap[n-1] + 1

                        # else:
                        #m = self.zone.parent.prev.cumulativeIndexMap[n]

                    else:
                        idxmap = None
                        #m = n

                if self.modeBox.currentData() == 2:
                    idxmap = self.shadow.cumulativeIndexMap
                    # if n > 0:
                    #m = self.zone.parent.cumulativeIndexMap[n-1] + 1

                    # else:
                    #m = self.zone.parent.cumulativeIndexMap[n]

            elif self._mode == 1:
                if self.modeBox.currentData() == 0:
                    if isinstance(self.shadow.prev, BaseFilter):
                        idxmap = self.shadow.prev.cumulativeIndexReverseMap
                        # if n > 0:
                        #m = self.zone.parent.prev.cumulativeIndexReverseMap[n-1] + 1

                        # else:
                        #m = self.zone.parent.prev.cumulativeIndexReverseMap[n]

                    else:
                        #m = n
                        idxmap = None

                if self.modeBox.currentData() == 2:
                    idxmap = self.shadow.indexMap
                    # if n > 0:
                    #m = self.zone.parent.indexMap[n-1] + 1

                    # else:
                    #m = self.zone.parent.indexMap[n]

            elif self._mode == 2:
                if self.modeBox.currentData() == 0:
                    if isinstance(self.shadow, BaseFilter):
                        idxmap = self.shadow.cumulativeIndexReverseMap

                    else:
                        idxmap = None
                    # if isinstance(self.zone.parent.prev, BaseFilter):
                        # if n > 0:
                        #m = self.zone.parent.cumulativeIndexReverseMap[n-1] + 1

                        # else:
                        #m = self.zone.parent.cumulativeIndexReverseMap[n]

                    # else:
                        #m = n

                if self.modeBox.currentData() == 1:
                    idxmap = self.shadow.reverseIndexMap
                    # if n > 0:
                    #m = self.zone.parent.reverseIndexMap[n-1] + 1

                    # else:
                    #m = self.zone.parent.reverseIndexMap[n]

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
                if isinstance(self.zone.parent.prev, BaseFilter):
                    if n > 0:
                        m = self.zone.parent.prev.cumulativeIndexReverseMap[n-1] + 1

                    else:
                        m = self.zone.parent.prev.cumulativeIndexReverseMap[n]

                else:
                    m = n

                J, zone = self.zone.parent.insertZoneAt(int(m))
                self.setZone(zone)

            else:
                prevzone = self.zone.prev
                self.zone.parent.removeZoneAt(self.zone.source.start)
                self.setZone(prevzone)
                self.slider.setValue(n)

        elif self._mode == 2:
            if n > self.zone.dest_start:
                if n > 0:
                    m = self.zone.parent.cumulativeIndexReverseMap[n-1] + 1

                else:
                    m = self.zone.parent.cumulativeIndexReverseMap[n]

                J, zone = self.zone.parent.insertZoneAt(int(m))
                self.setZone(zone)

            else:
                prevzone = self.zone.prev
                self.zone.parent.removeZoneAt(self.zone.source.start)
                self.setZone(prevzone)
                self.slider.setValue(n)

        self.isModified()

    @pyqtSlot()
    def prevZone(self):
        self.setZone(self.zone.prev)

    @pyqtSlot()
    def nextZone(self):
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
        #self.imageView.resize(pixmap.width(), pixmap.height())

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

        self.isModified()

    def zoneNotModified(self):
        self.zonemodified = False

        if hasattr(self, "applyZoneBtn") and self.applyZoneBtn is not None:
            self.applyZoneBtn.setDisabled(True)

        if hasattr(self, "resetZoneBtn") and self.resetZoneBtn is not None:
            self.resetZoneBtn.setDisabled(True)

    def apply(self):
        self.applyZone()
        super().apply()
