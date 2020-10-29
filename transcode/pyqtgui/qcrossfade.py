#!/usr/bin/python
from PyQt5.QtCore import pyqtSlot, QTime
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QLabel, QVBoxLayout, QHBoxLayout, QWidget, QCheckBox)

from transcode.filters.crossfade import CrossFade
from transcode.filters.base import BaseFilter

from .qimageview import QImageView
from .qfilterconfig import QFilterConfig
from .qframeselect import QFrameSelect


class QCrossFade(QFilterConfig):
    allowedtypes = ("video", "audio")

    def _createControls(self):
        self.setWindowTitle("Configure Crossfade")

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.sourceWidget = QWidget(self)

        self.source1Selection = self.createSourceControl(self.sourceWidget)
        self.source1Selection.setSelectFunc(self.isValidSource1)
        self.source1Selection.currentDataChanged.connect(self.setFilterSource1)
        self.source1Fade = QCheckBox("Fade Out", self)
        self.source1Fade.stateChanged.connect(self.setSource1Fade)

        self.source2Selection = self.createSourceControl(self.sourceWidget)
        self.source2Selection.setSelectFunc(self.isValidSource2)
        self.source2Selection.currentDataChanged.connect(self.setFilterSource2)
        self.source2Fade = QCheckBox("Fade In", self)
        self.source2Fade.stateChanged.connect(self.setSource2Fade)

        srclayout = QVBoxLayout()
        src1layout = QHBoxLayout()
        src2layout = QHBoxLayout()
        srclayout.addLayout(src1layout)
        srclayout.addLayout(src2layout)

        src1layout.addWidget(QLabel("Source 1: ", self.sourceWidget))
        src1layout.addWidget(self.source1Selection)
        src1layout.addWidget(self.source1Fade)

        src2layout.addWidget(QLabel("Source 2: ", self.sourceWidget))
        src2layout.addWidget(self.source2Selection)
        src2layout.addWidget(self.source2Fade)

        self.sourceWidget.setLayout(srclayout)
        layout.addWidget(self.sourceWidget)

        self.imageView = QImageView(self)
        self.frameSelect = QFrameSelect(self)
        self.frameSelect.frameSelectionChanged.connect(
            self.handleFrameSelectionChange)
        layout.addWidget(self.imageView)
        layout.addWidget(self.frameSelect)

        self._prepareDlgButtons()

    def _resetSourceModels(self):
        self._resetSourceModel(self.source1Selection)
        self._resetSourceModel(self.source2Selection)

    @pyqtSlot(int, QTime)
    def handleFrameSelectionChange(self, n, t):
        self.setFrame(n)

    def setSource1Fade(self, value):
        if value:
            self.shadow.flags &= ~1

        else:
            self.shadow.flags |= 1

        self.setFrame(self.frameSelect.slider.value())
        self.isModified()

    def setSource2Fade(self, value):
        if value:
            self.shadow.flags &= ~2

        else:
            self.shadow.flags |= 2

        self.setFrame(self.frameSelect.slider.value())
        self.isModified()

    def setFrame(self, n):
        try:
            frame = next(self.shadow.iterFrames(n, whence="framenumber"))

        except StopIteration:
            self.imageView.setFrame(
                QPixmap(self.shadow.width, self.shadow.height))
            return

        im = frame.to_image()
        pixmap = im.toqpixmap()
        self.imageView.setFrame(pixmap)

    def createNewFilterInstance(self):
        return CrossFade()

    def _resetSourceControls(self):
        self._showSourceControls(self.inputFiles or self.availableFilters)
        self._setSourceSelection(self.source1Selection, self.shadow.source1)
        self._setSourceSelection(self.source2Selection, self.shadow.source2)

    def _resetControls(self):
        if self.shadow is not None:
            self.source1Fade.blockSignals(True)
            self.source1Fade.setCheckState(0 if (1 & self.shadow.flags) else 2)
            self.source1Fade.blockSignals(False)

            self.source2Fade.blockSignals(True)
            self.source2Fade.setCheckState(0 if (2 & self.shadow.flags) else 2)
            self.source2Fade.blockSignals(False)

            self.frameSelect.setVisible(self.shadow.type == "video")
            self.imageView.setVisible(self.shadow.type == "video")

            if self.shadow.type == "video":
                self.frameSelect.setPtsTimeArray(self.shadow.pts_time)
                self.setFrame(0)

            self.setEnabled(True)

        else:
            self.source1Fade.blockSignals(True)
            self.source1Fade.setCheckState(2)
            self.source1Fade.blockSignals(False)

            self.source2Fade.blockSignals(True)
            self.source2Fade.setCheckState(2)
            self.source2Fade.blockSignals(False)

            self.frameSelect.setVisible(False)
            self.imageView.setVisible(False)
            self.setEnabled(False)

    def setFilterSource1(self, source):
        self.imageView.setVisible(
            source is not None and source.type == "video")
        self.shadow.source1 = source
        self.isModified()

        if source is not None and self.shadow.source2 is not None and source.type == "video":
            self.frameSelect.setPtsTimeArray(source.pts_time)
            self.setFrame(self.frameSelect.slider.value())

    def setFilterSource2(self, source):
        self.imageView.setVisible(
            source is not None and source.type == "video")
        self.shadow.source2 = source
        self.isModified()

        if source is not None and self.shadow.source1 is not None and source.type == "video":
            self.frameSelect.setPtsTimeArray(source.pts_time)
            self.setFrame(self.frameSelect.slider.value())

    def isValidSource1(self, other):
        if other is self.filter:
            return False

        if isinstance(other, BaseFilter) and self.filter in other.dependencies:
            return False

        if self.shadow.source2 is None:
            return other.type in ("video", "audio")

        elif self.shadow.source2.type == "video":
            return self.shadow.source2.framecount == other.framecount and \
                self.shadow.source2.width == other.width and \
                self.shadow.source2.height == other.height and \
                (abs(self.shadow.source2.pts_time - other.pts_time) < 0.008).all()

        elif self.shadow.source2.type == "audio":
            return self.shadow.source2.channels == other.channels and \
                abs(self.shadow.source2.duration - other.duration) < 0.00001

    def isValidSource2(self, other):
        if other is self.filter:
            return False

        if isinstance(other, BaseFilter) and self.filter in other.dependencies:
            return False

        if self.shadow.source1 is None:
            return other.type in ("video", "audio")

        elif self.shadow.source1.type == "video":
            return self.shadow.source1.framecount == other.framecount and \
                self.shadow.source1.width == other.width and \
                self.shadow.source1.height == other.height and \
                (abs(self.shadow.source1.pts_time - other.pts_time) < 0.008).all()

        elif self.shadow.source1.type == "audio":
            return self.shadow.source1.channels == other.channels and \
                abs(self.shadow.source1.duration - other.duration) < 0.00001
