#!/usr/bin/python
from PyQt5.QtCore import pyqtSlot, QTime
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import (QLabel, QVBoxLayout, QHBoxLayout, QWidget, QCheckBox)

from . import CrossFade
from ..base import BaseFilter

from transcode.pyqtgui.qimageview import QImageView
from transcode.pyqtgui.qfilterconfig import QFilterConfig
from transcode.pyqtgui.qframeselect import QFrameSelect


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
            self.filtercopy.flags &= ~1

        else:
            self.filtercopy.flags |= 1

        if self.filtercopy.prev is not None and self.filtercopy.prev.type == "video":
            self.setFrame(self.frameSelect.slider.value())

        self.isModified()

    def setSource2Fade(self, value):
        if value:
            self.filtercopy.flags &= ~2

        else:
            self.filtercopy.flags |= 2

        if self.filtercopy.prev is not None and self.filtercopy.prev.type == "video":
            self.setFrame(self.frameSelect.slider.value())

        self.isModified()

    def setFrame(self, n):
        try:
            frame = next(self.filtercopy.iterFrames(n, whence="framenumber"))

        except StopIteration:
            self.imageView.setFrame(
                QPixmap(self.filtercopy.width, self.filtercopy.height))
            return

        im = frame.to_image()
        pixmap = im.convert("RGBA").toqpixmap()
        self.imageView.setFrame(pixmap)

    def createNewFilterInstance(self):
        return CrossFade()

    def _resetSourceControls(self):
        self._showSourceControls(self.inputFiles or self.availableFilters)
        self._setSourceSelection(self.source1Selection, self.filtercopy.source1)
        self._setSourceSelection(self.source2Selection, self.filtercopy.source2)

    def _resetControls(self):
        if self.filtercopy is not None:
            self.source1Fade.blockSignals(True)
            self.source1Fade.setCheckState(0 if (1 & self.filtercopy.flags) else 2)
            self.source1Fade.blockSignals(False)

            self.source2Fade.blockSignals(True)
            self.source2Fade.setCheckState(0 if (2 & self.filtercopy.flags) else 2)
            self.source2Fade.blockSignals(False)

            self.frameSelect.setVisible(self.filtercopy.type == "video")
            self.imageView.setVisible(self.filtercopy.type == "video")

            if self.filtercopy.type == "video":
                self.frameSelect.setPtsTimeArray(self.filtercopy.pts_time)
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
        self.filtercopy.source1 = source
        self.isModified()

        if source is not None and self.filtercopy.source2 is not None and source.type == "video":
            self.frameSelect.setPtsTimeArray(source.pts_time)
            self.setFrame(self.frameSelect.slider.value())

    def setFilterSource2(self, source):
        self.imageView.setVisible(
            source is not None and source.type == "video")
        self.filtercopy.source2 = source
        self.isModified()

        if source is not None and self.filtercopy.source1 is not None and source.type == "video":
            self.frameSelect.setPtsTimeArray(source.pts_time)
            self.setFrame(self.frameSelect.slider.value())

    def isValidSource1(self, other):
        if other is self.filter:
            return False

        if isinstance(other, BaseFilter) and self.filter in other.dependencies:
            return False

        if self.filtercopy.source2 is None:
            return other.type in ("video", "audio")

        if other.type is None:
            return True

        elif self.filtercopy.source2.type == "video":
            return self.filtercopy.source2.framecount == other.framecount and \
                self.filtercopy.source2.width == other.width and \
                self.filtercopy.source2.height == other.height and \
                (abs(self.filtercopy.source2.pts_time - other.pts_time) < 0.008).all()

        elif self.filtercopy.source2.type == "audio":
            return self.filtercopy.source2.channels == other.channels and \
                abs(self.filtercopy.source2.duration - other.duration) < 0.00001

    def isValidSource2(self, other):
        if other is self.filter:
            return False

        if isinstance(other, BaseFilter) and self.filter in other.dependencies:
            return False

        if other.type is None:
            return True

        if self.filtercopy.source1 is None:
            return other.type in ("video", "audio")

        elif self.filtercopy.source1.type == "video":
            return self.filtercopy.source1.framecount == other.framecount and \
                self.filtercopy.source1.width == other.width and \
                self.filtercopy.source1.height == other.height and \
                (abs(self.filtercopy.source1.pts_time - other.pts_time) < 0.008).all()

        elif self.filtercopy.source1.type == "audio":
            return self.filtercopy.source1.channels == other.channels and \
                abs(self.filtercopy.source1.duration - other.duration) < 0.00001
