#!/usr/bin/python
from PIL import Image
from PyQt5.QtCore import Qt, pyqtSlot, QRegExp, QTime
from PyQt5.QtGui import QRegExpValidator, QPen, QColor
from PyQt5.QtWidgets import (QAction, QLabel, QSpinBox, QGridLayout,
                             QVBoxLayout, QHBoxLayout, QLineEdit, QScrollArea,
                             QWidget, QComboBox)

from functools import partial
from fractions import Fraction as QQ
import regex

from . import Crop, Resize, CropScenes
from transcode.filters.video.scenes import Scenes
from transcode.filters.filterchain import FilterChain
from transcode.pyqtgui.qzones import ZoneDlg
from transcode.pyqtgui.qframetablecolumn import ZoneCol
from transcode.pyqtgui.qimageview import QImageView
from transcode.pyqtgui.qfilterconfig import QFilterConfig
from transcode.pyqtgui.qframeselect import QFrameSelect


class QCrop(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QGridLayout()
        self.setLayout(layout)

        self.cropTop = QSpinBox(self)
        self.cropLeft = QSpinBox(self)
        self.cropRight = QSpinBox(self)
        self.cropBottom = QSpinBox(self)

        self.cropTop.setSingleStep(2)
        self.cropTop.setMinimum(0)
        self.cropTop.valueChanged.connect(self.setCropTop)

        self.cropBottom.setSingleStep(2)
        self.cropBottom.setMinimum(0)
        self.cropBottom.valueChanged.connect(self.setCropBottom)

        self.cropLeft.setSingleStep(2)
        self.cropLeft.setMinimum(0)
        self.cropLeft.valueChanged.connect(self.setCropLeft)

        self.cropRight.setSingleStep(2)
        self.cropRight.setMinimum(0)
        self.cropRight.valueChanged.connect(self.setCropRight)

        self.scrollArea = QScrollArea(self)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        self.imageView = QImageView(self)
        self.scrollArea.setWidget(self.imageView)
        self.imageView.setPaintHook(self._paintHook)

        tlayout = QHBoxLayout()
        tlayout.addStretch()
        tlayout.addWidget(self.cropTop)
        tlayout.addStretch()

        layout.addLayout(tlayout, 0, 1)
        layout.addWidget(self.cropLeft, 1, 0)
        layout.addWidget(self.scrollArea, 1, 1)
        layout.addWidget(self.cropRight, 1, 2)

        blayout = QHBoxLayout()
        blayout.addStretch()
        blayout.addWidget(self.cropBottom)
        blayout.addStretch()

        layout.addLayout(blayout, 2, 1)

        self.setFrameWidth(1920)
        self.setFrameHeight(720)

    def setFrameWidth(self, width):
        self._width = width
        self.cropRight.setMaximum(width - self.cropLeft.value() - 2)
        self.cropLeft.setMaximum(width - self.cropRight.value() - 2)

    def setFrameHeight(self, height):
        self._height = height
        self.cropTop.setMaximum(height - self.cropBottom.value() - 2)
        self.cropBottom.setMaximum(height - self.cropTop.value() - 2)

    def frameWidth(self):
        return self._width

    def frameHeight(self):
        return self._height

    @pyqtSlot(int)
    def setCropTop(self, croptop):
        self.cropBottom.setMaximum(self.frameHeight() - croptop - 2)
        self.imageView.update()

    @pyqtSlot(int)
    def setCropBottom(self, cropbottom):
        self.cropTop.setMaximum(self.frameHeight() - cropbottom - 2)
        self.imageView.update()

    @pyqtSlot(int)
    def setCropLeft(self, cropleft):
        self.cropRight.setMaximum(self.frameWidth() - cropleft - 2)
        self.imageView.update()

    @pyqtSlot(int)
    def setCropRight(self, cropright):
        self.cropLeft.setMaximum(self.frameWidth() - cropright - 2)
        self.imageView.update()

    def setFrame(self, frame):
        self.setFrameWidth(max(2, frame.width()))
        self.setFrameHeight(max(2, frame.height()))
        self.imageView.setFrame(frame)
        self.imageView.resize(frame.width(), frame.height())

    def _paintHook(self, widget, event, painter):
        w, h = widget.pixmap().width(), widget.pixmap().height()
        dar = w/h

        W = widget.width()
        H = widget.height()

        WW, HH = min([(W, W/dar), (H*dar, H)])

        if WW < W:
            x0, y0 = ((W - WW)/2, 0)

        else:
            x0, y0 = (0, (H - HH)/2)

        zoom = WW/w

        if widget.pixmap() is not None:
            if zoom >= 8:
                pen = QPen(Qt.gray, 1)
                painter.setPen(pen)

                for j in range(0, w + 1):
                    J = j*zoom
                    painter.drawLine(x0 + J, y0, x0 + J, y0 + H)

                for j in range(0, h + 1):
                    J = j*zoom
                    painter.drawLine(x0, y0 + J, x0 + W, y0 + J)

        pen = QPen(Qt.red, 1)
        painter.setPen(pen)

        j = k = int(zoom < 8)

        painter.drawLine(x0 + self.cropLeft.value()*zoom - j,
                         y0, x0 + self.cropLeft.value()*zoom - j, y0 + H)
        painter.drawLine(x0 + W - self.cropRight.value()*zoom,
                         y0, x0 + W - self.cropRight.value()*zoom, y0 + H)
        painter.drawLine(x0, y0 + self.cropTop.value()*zoom - k,
                         x0 + W, y0 + self.cropTop.value()*zoom - k)
        painter.drawLine(x0, y0 + H - self.cropBottom.value()
                         * zoom, x0 + W, y0 + H - self.cropBottom.value()*zoom)


class QResize(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        gridlayout = QGridLayout()
        self.setLayout(gridlayout)

        widthLabel = QLabel("Width:", self)

        self.width = QSpinBox(self)
        self.width.setSingleStep(16)
        self.width.setSpecialValueText("No change")
        self.width.setMaximum(4*1920)
        self.width.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        heightLabel = QLabel("Height:", self)

        self.height = QSpinBox(self)
        self.height.setSingleStep(16)
        self.height.setSpecialValueText("No change")
        self.height.setMaximum(4*1080)
        self.height.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        regex = QRegExp(r"^(\d+(?:\.\d+)?|\.\d+|\d+/\d+)$")
        validator = QRegExpValidator(regex)

        sarLabel = QLabel("SAR:", self)

        self.sar = QLineEdit(self)
        self.sar.setText("1")
        self.sar.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sar.setValidator(validator)

        resampleLabel = QLabel("Resampling:", self)

        self.resample = QComboBox(self)
        self.resample.addItem("Nearest Neighbor", Image.NEAREST)
        self.resample.addItem("Bilinear", Image.BILINEAR)
        self.resample.addItem("Bicubic", Image.BICUBIC)
        self.resample.addItem("Lanczos", Image.LANCZOS)

        gridlayout.addWidget(widthLabel, 0, 0)
        gridlayout.addWidget(self.width, 0, 1)
        gridlayout.addWidget(heightLabel, 1, 0)
        gridlayout.addWidget(self.height, 1, 1)
        gridlayout.addWidget(sarLabel, 2, 0)
        gridlayout.addWidget(self.sar, 2, 1)
        gridlayout.addWidget(resampleLabel, 3, 0)
        gridlayout.addWidget(self.resample, 3, 1)

        gridlayout.setRowMinimumHeight(0, 32)
        gridlayout.setRowMinimumHeight(1, 32)
        gridlayout.setRowMinimumHeight(2, 32)
        gridlayout.setRowMinimumHeight(3, 32)
        gridlayout.setHorizontalSpacing(4)

        gridlayout.setColumnMinimumWidth(1, 96)

    def setFrameWidth(self, width):
        self._width = width
        self.cropRight.setMaximum(width - self.cropLeft.value() - 2)
        self.cropLeft.setMaximum(width - self.cropRight.value() - 2)

    def setFrameHeight(self, height):
        self._height = height
        self.cropTop.setMaximum(height - self.cropBottom.value() - 2)
        self.cropBottom.setMaximum(height - self.cropTop.value() - 2)

    def frameWidth(self):
        return self._width

    def frameHeight(self):
        return self._height

    @pyqtSlot(int)
    def setCropTop(self, croptop):
        self.cropBottom.setMaximum(self.frameHeight() - croptop - 2)
        self.imageView.update()

    @pyqtSlot(int)
    def setCropBottom(self, cropbottom):
        self.cropTop.setMaximum(self.frameHeight() - cropbottom - 2)
        self.imageView.update()

    @pyqtSlot(int)
    def setCropLeft(self, cropleft):
        self.cropRight.setMaximum(self.frameWidth() - cropleft - 2)
        self.imageView.update()

    @pyqtSlot(int)
    def setCropRight(self, cropright):
        self.cropLeft.setMaximum(self.frameWidth() - cropright - 2)
        self.imageView.update()

    def setFrame(self, frame):
        self.setFrameWidth(max(2, frame.width()))
        self.setFrameHeight(max(2, frame.height()))
        self.imageView.setFrame(frame)
        self.imageView.resize(frame.width(), frame.height())

    def _paintHook(self, widget, event, painter):
        w, h = widget.pixmap().width(), widget.pixmap().height()
        dar = w/h

        W = widget.width()
        H = widget.height()

        WW, HH = min([(W, W/dar), (H*dar, H)])

        if WW < W:
            x0, y0 = ((W - WW)/2, 0)

        else:
            x0, y0 = (0, (H - HH)/2)

        zoom = WW/w

        if widget.pixmap() is not None:
            if zoom >= 8:
                pen = QPen(Qt.gray, 1)
                painter.setPen(pen)

                for j in range(0, w + 1):
                    J = j*zoom
                    painter.drawLine(x0 + J, y0, x0 + J, y0 + H)

                for j in range(0, h + 1):
                    J = j*zoom
                    painter.drawLine(x0, y0 + J, x0 + W, y0 + J)

        pen = QPen(Qt.red, 1)
        painter.setPen(pen)

        j = k = int(zoom < 8)

        painter.drawLine(x0 + self.cropLeft.value()*zoom - j,
                         y0, x0 + self.cropLeft.value()*zoom - j, y0 + H)
        painter.drawLine(x0 + W - self.cropRight.value()*zoom,
                         y0, x0 + W - self.cropRight.value()*zoom, y0 + H)
        painter.drawLine(x0, y0 + self.cropTop.value()*zoom - k,
                         x0 + W, y0 + self.cropTop.value()*zoom - k)
        painter.drawLine(x0, y0 + H - self.cropBottom.value()
                         * zoom, x0 + W, y0 + H - self.cropBottom.value()*zoom)


class CropDlg(QFilterConfig):
    allowedtypes = ("video",)

    def _createControls(self):
        self.setWindowTitle("Configure Crop")

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

        self.cropWidget = QCrop(self)
        self.cropWidget.cropRight.valueChanged.connect(self.setCropRight)
        self.cropWidget.cropLeft.valueChanged.connect(self.setCropLeft)
        self.cropWidget.cropTop.valueChanged.connect(self.setCropTop)
        self.cropWidget.cropBottom.valueChanged.connect(self.setCropBottom)

        self.slider = QFrameSelect(self)
        self.slider.frameSelectionChanged.connect(self.loadFrame)

        layout.addWidget(self.cropWidget)
        layout.addWidget(self.slider)

        self._prepareDlgButtons()

    @pyqtSlot(int, QTime)
    def loadFrame(self, n, t):
        if self.filtercopy.prev is not None:
            frame = next(
                self.filtercopy.prev.iterFrames(n, whence="framenumber"))

            im = frame.to_image()
            pixmap = im.convert("RGBA").toqpixmap()
            self.cropWidget.setFrame(pixmap)
            self.cropWidget.resize(pixmap.size())

    def createNewFilterInstance(self):
        return Crop()

    def _prevChanged(self, source):
        self._resetControlMaximums()
        self.slider.setPtsTimeArray(source.pts_time)
        self.loadFrame(self.slider.slider.value(),
                       self.slider.currentTime.time())

    def _resetControlMaximums(self):
        if self.filtercopy.prev is not None:
            self.cropWidget.cropTop.setMaximum(
                self.filtercopy.prev.height - self.filtercopy.cropbottom - 2)
            self.cropWidget.cropBottom.setMaximum(
                self.filtercopy.prev.height - self.filtercopy.croptop - 2)
            self.cropWidget.cropRight.setMaximum(
                self.filtercopy.prev.width - self.filtercopy.cropleft - 2)
            self.cropWidget.cropLeft.setMaximum(
                self.filtercopy.prev.width - self.filtercopy.cropright - 2)

    def _resetControls(self):
        self.cropWidget.cropTop.blockSignals(True)
        self.cropWidget.cropTop.setValue(self.filtercopy.croptop)
        self.cropWidget.cropTop.blockSignals(False)

        self.cropWidget.cropBottom.blockSignals(True)
        self.cropWidget.cropBottom.setValue(self.filtercopy.cropbottom)
        self.cropWidget.cropBottom.blockSignals(False)

        self.cropWidget.cropLeft.blockSignals(True)
        self.cropWidget.cropLeft.setValue(self.filtercopy.cropleft)
        self.cropWidget.cropLeft.blockSignals(False)

        self.cropWidget.cropRight.blockSignals(True)
        self.cropWidget.cropRight.setValue(self.filtercopy.cropright)
        self.cropWidget.cropRight.blockSignals(False)

        if self.filtercopy.prev is not None:
            self.cropWidget.setFrameWidth(self.filtercopy.prev.width)
            self.cropWidget.setFrameHeight(self.filtercopy.prev.height)
            self.slider.setPtsTimeArray(self.filtercopy.prev.pts_time)
            self.loadFrame(self.slider.slider.value(), QTime())

        else:
            self.cropWidget.setFrameWidth(1920)
            self.cropWidget.setFrameHeight(1080)
            self.slider.setPtsTimeArray(None)

    @pyqtSlot(int)
    def setCropTop(self, croptop):
        self.filtercopy.croptop = croptop
        self.isModified()

    @pyqtSlot(int)
    def setCropBottom(self, cropbottom):
        self.filtercopy.cropbottom = cropbottom
        self.isModified()

    @pyqtSlot(int)
    def setCropLeft(self, cropleft):
        self.filtercopy.cropleft = cropleft
        self.isModified()

    @pyqtSlot(int)
    def setCropRight(self, cropright):
        self.filtercopy.cropright = cropright
        self.isModified()


class CropZoneDlg(ZoneDlg):
    allowedtypes = ("video",)

    def createNewFilterInstance(self):
        return CropScenes()

    def _createImageView(self, layout=None, index=None):
        if layout is None:
            layout = self.layout()

        self.cropWidget = QCrop(self)
        self.imageView = self.cropWidget.imageView

        self.cropWidget.cropRight.valueChanged.connect(self.setCropRight)
        self.cropWidget.cropLeft.valueChanged.connect(self.setCropLeft)
        self.cropWidget.cropTop.valueChanged.connect(self.setCropTop)
        self.cropWidget.cropBottom.valueChanged.connect(self.setCropBottom)

        if isinstance(layout, QGridLayout):
            layout.addWidget(self.cropWidget, *index)

        elif isinstance(layout, QScrollArea):
            layout.setWidget(self.cropWidget)

        elif index is not None:
            layout.insertWidget(index, self.cropWidget)

        else:
            layout.addWidget(self.cropWidget)

    def _createGlobalControls(self, layout=None, index=None):
        if layout is None:
            layout = self.layout()

        hlayout = QHBoxLayout()
        self.resizeWidget = QResize(self)
        self.resizeWidget.width.valueChanged.connect(self.setWidth)
        self.resizeWidget.height.valueChanged.connect(self.setHeight)
        self.resizeWidget.sar.textChanged.connect(self.setSar)
        self.resizeWidget.resample.currentIndexChanged.connect(
            self.setResample)

        hlayout.addStretch()
        hlayout.addWidget(self.resizeWidget)
        hlayout.addStretch()

        if isinstance(layout, QGridLayout):
            layout.addLayout(hlayout, *index)

        elif index is not None:
            layout.insertLayout(index, hlayout)

        else:
            layout.addLayout(hlayout)

    def _resetControlMaximums(self):
        if self.filtercopy.prev is not None:
            self.cropWidget.cropTop.setMaximum(
                self.filtercopy.prev.height - self.zonecopy.cropbottom - 2)
            self.cropWidget.cropBottom.setMaximum(
                self.filtercopy.prev.height - self.zonecopy.croptop - 2)
            self.cropWidget.cropRight.setMaximum(
                self.filtercopy.prev.width - self.zonecopy.cropleft - 2)
            self.cropWidget.cropLeft.setMaximum(
                self.filtercopy.prev.width - self.zonecopy.cropright - 2)

    def _resetZoneControls(self):
        self.cropWidget.cropTop.blockSignals(True)
        self.cropWidget.cropTop.setValue(self.zonecopy.croptop)
        self.cropWidget.cropTop.blockSignals(False)

        self.cropWidget.cropBottom.blockSignals(True)
        self.cropWidget.cropBottom.setValue(self.zonecopy.cropbottom)
        self.cropWidget.cropBottom.blockSignals(False)

        self.cropWidget.cropLeft.blockSignals(True)
        self.cropWidget.cropLeft.setValue(self.zonecopy.cropleft)
        self.cropWidget.cropLeft.blockSignals(False)

        self.cropWidget.cropRight.blockSignals(True)
        self.cropWidget.cropRight.setValue(self.zonecopy.cropright)
        self.cropWidget.cropRight.blockSignals(False)

    def _resetGlobalControls(self):
        self.resizeWidget.height.blockSignals(True)
        self.resizeWidget.height.setValue(self.filtercopy.height or 0)
        self.resizeWidget.height.blockSignals(False)

        self.resizeWidget.width.blockSignals(True)
        self.resizeWidget.width.setValue(self.filtercopy.width or 0)
        self.resizeWidget.width.blockSignals(False)

        self.resizeWidget.sar.blockSignals(True)
        self.resizeWidget.sar.setText(str(self.filtercopy.sar))
        self.resizeWidget.sar.blockSignals(False)

        idx = self.resizeWidget.resample.findData(self.filtercopy.sar)

        if idx >= 0:
            self.resizeWidget.resample.blockSignals(True)
            self.resizeWidget.resample.setCurrentIndex(idx)
            self.resizeWidget.resample.blockSignals(False)

    # TODO: Implement zoom in, zoom out, zoom original

    @pyqtSlot(int, QTime)
    def loadFrame(self, n, t):
        if self._mode == 1:
            self.imageView.setPaintHook(self.cropWidget._paintHook)

        else:
            self.imageView.setPaintHook(None)

        super().loadFrame(n, t)
        self.imageView.resize(self.imageView.pixmap().size())

    @pyqtSlot(int)
    def setCropTop(self, croptop):
        self.zonecopy.croptop = croptop
        self.zoneModified()

    @pyqtSlot(int)
    def setCropBottom(self, cropbottom):
        self.zonecopy.cropbottom = cropbottom
        self.zoneModified()

    @pyqtSlot(int)
    def setCropLeft(self, cropleft):
        self.zonecopy.cropleft = cropleft
        self.zoneModified()

    @pyqtSlot(int)
    def setCropRight(self, cropright):
        self.zonecopy.cropright = cropright
        self.zoneModified()

    @pyqtSlot(int)
    def setHeight(self, height):
        self.filtercopy.height = height or None
        self.isModified()

    @pyqtSlot(int)
    def setWidth(self, width):
        self.filtercopy.width = width or None
        self.isModified()

    def zoneModified(self):
        if self._mode == 2 and self.filtercopy.prev is not None:
            self.loadFrame(self.slider.slider.value(),
                           self.slider.currentTime.time())

        super().zoneModified()

    def zoneNotModified(self):
        super().zoneNotModified()

        if self._mode == 2 and self.filtercopy.prev is not None:
            self.loadFrame(self.slider.slider.value(),
                           self.slider.currentTime.time())

        else:
            self.imageView.update()

    @pyqtSlot(str)
    def setSar(self, sar):
        if not regex.match(r"^(\d+(?:\.\d+)?|\.\d+|\d+/\d+)$", sar):
            return

        if regex.match(r"^\d+/\d+$", sar):
            sar = QQ(sar)

        elif regex.match(r"^\d+$", sar):
            sar = int(sar)

        else:
            sar = float(sar)

        self.filtercopy.sar = sar
        self.isModified()

    @pyqtSlot(int)
    def setResample(self, resample):
        resample = self.resizeWidget.resample.currentData()
        self.filtercopy.resample = resample
        self.isModified()

    def _prevChanged(self, source):
        self._resetControlMaximums()
        self.slider.setPtsTimeArray(source.pts_time)
        self.loadFrame(self.slider.slider.value(),
                       self.slider.currentTime.time())

        if self.filtercopy.height is None:
            self.resizeWidget.height.setValue(source.height)

        if self.filtercopy.width is None:
            self.resizeWidget.width.setValue(source.width)


class ResizeDlg(QFilterConfig):
    allowedtypes = ("video",)

    def _createControls(self):
        self.setWindowTitle("Configure Resize")

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        self.sourceWidget = QWidget(self)
        srclayout = QHBoxLayout()
        self.sourceWidget.setLayout(srclayout)

        self.sourceSelection = self.createSourceControl(self.sourceWidget)
        self.sourceSelection.currentDataChanged.connect(self.setFilterSource)

        srclayout.setContentsMargins(0, 0, 0, 0)
        srclayout.addWidget(QLabel("Source: "))
        srclayout.addWidget(self.sourceSelection)

        layout.addWidget(self.sourceWidget)

        self.resizeWidget = QResize(self)
        self.resizeWidget.width.valueChanged.connect(self.setWidth)
        self.resizeWidget.height.valueChanged.connect(self.setHeight)
        self.resizeWidget.sar.textChanged.connect(self.setSar)
        self.resizeWidget.resample.currentIndexChanged.connect(
            self.setResample)
        layout.addWidget(self.resizeWidget)

        self._prepareDlgButtons()

    def createNewFilterInstance(self):
        return Resize()

    def _resetControls(self):
        self.resizeWidget.height.blockSignals(True)
        self.resizeWidget.height.setValue(self.filtercopy.height or 0)
        self.resizeWidget.height.blockSignals(False)

        self.resizeWidget.width.blockSignals(True)
        self.resizeWidget.width.setValue(self.filtercopy.width or 0)
        self.resizeWidget.width.blockSignals(False)

        self.resizeWidget.sar.blockSignals(True)
        self.resizeWidget.sar.setText(str(self.filtercopy.sar))
        self.resizeWidget.sar.blockSignals(False)

        idx = self.resizeWidget.resample.findData(self.filtercopy.sar)

        if idx >= 0:
            self.resizeWidget.resample.blockSignals(True)
            self.resizeWidget.resample.setCurrentIndex(idx)
            self.resizeWidget.resample.blockSignals(False)

    def _prevChanged(self, source):
        if self.filtercopy.height is None:
            self.resizeWidget.height.setValue(source.height)

        if self.filtercopy.width is None:
            self.resizeWidget.width.setValue(source.width)

    @pyqtSlot(int)
    def setHeight(self, height):
        self.filtercopy.height = height or None
        self.isModified()

    @pyqtSlot(int)
    def setWidth(self, width):
        self.filtercopy.width = width or None
        self.isModified()

    @pyqtSlot(str)
    def setSar(self, sar):
        if not regex.match(r"^(\d+(?:\.\d+)?|\.\d+|\d+/\d+)$", sar):
            return

        if regex.match(r"^\d+/\d+$", sar):
            sar = QQ(sar)

        elif regex.match(r"^\d+$", sar):
            sar = int(sar)

        else:
            sar = float(sar)

        self.filtercopy.sar = sar
        self.isModified()

    @pyqtSlot(int)
    def setResample(self, resample):
        resample = self.resizeWidget.resample.currentData()
        self.filtercopy.resample = resample
        self.isModified()


class CropResizeCol(ZoneCol):
    bgcolor = QColor(255, 128, 64)
    bgcoloralt = QColor(255, 255, 255)
    fgcolor = QColor(0, 0, 0)
    fgcoloralt = QColor(160, 160, 160)
    headerdisplay = "Crop"
    width = 128

    def display(self, index, obj):
        J, zone = self.filter.zoneAt(obj)
        return (f"{J} ({zone.croptop}, {zone.cropbottom}, "
                f"{zone.cropleft}, {zone.cropright})")

    def createContextMenu(self, table, index, obj):
        menu = ZoneCol.createContextMenu(self, table, index, obj)
        menu.addSeparator()

        if isinstance(self.filter.parent, FilterChain):
            for scenes in self.filter.parent:
                if isinstance(scenes, Scenes):
                    zoneatscenes = QAction(
                        "Create zones from scenes", table,
                        triggered=partial(
                            self.zoneAtScenes, table=table, scenes=scenes))
                    break

            else:
                zoneatscenes = QAction(
                    "Create zones from scenes", table,
                    triggered=partial(
                        self.zoneAtScenes, table=table, scenes=None))

                zoneatscenes.setEnabled(False)

        else:
            zoneatscenes = QAction(
                "Create zones from scenes", table,
                triggered=partial(
                    self.zoneAtScenes, table=table, scenes=None))

            zoneatscenes.setEnabled(False)

        menu.addAction(zoneatscenes)

        configure = QAction("Configure zone...", table, triggered=partial(
            self.createDlg, table=table, index=index))
        menu.addAction(configure)
        return menu

    def createDlg(self, table, index):
        J, zone = self.filter.zoneAt(index.row())
        dlg = CropZoneDlg(table)
        dlg.setFilter(self.filter, True)
        dlg.setZone(zone)
        dlg.contentsModified.connect(table.contentsModified)
        dlg.slider.setValue(self.filter.cumulativeIndexMap[index.row()])
        dlg.exec_()

    def zoneAtScenes(self, table, scenes):
        for scene in scenes:
            J, p = self.filter.zoneAt(scene.src_start)

            if p.src_start == scene.src_start:
                continue

            self.filter.insertZoneAt(
                scene.src_start, croptop=p.croptop, cropbottom=p.cropbottom,
                cropleft=p.cropleft, cropright=p.cropright)

        table.contentsModified.emit()
