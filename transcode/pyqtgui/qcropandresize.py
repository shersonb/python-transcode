#!/usr/bin/python
from PIL import Image
from PyQt5.QtCore import QDir, Qt, QModelIndex, pyqtSignal, pyqtSlot, pyqtBoundSignal, QThread, QRegExp, QRect
from PyQt5.QtGui import QRegExpValidator, QImage, QPainter, QPalette, QPixmap, QColor, QFont, QBrush, QPen, QStandardItemModel, QIcon
from PyQt5.QtWidgets import (QMenu, QAction, QLabel, QSpinBox, QDoubleSpinBox, QGridLayout, QVBoxLayout, QHBoxLayout,
                             QPushButton, QDialog, QSlider, QStyleOptionSlider, QStyle, QLineEdit, QScrollArea, QAbstractItemView)

import numpy
from numpy import sqrt
from functools import partial
from fractions import Fraction as QQ
import qtable
import regex

from transcode.filters.video.cropandresize import CropZone
from transcode.filters.video.scenes import Scenes
from transcode.filters.filterchain import FilterChain
from .qzones import ZoneDlg, BaseShadowZone
from .qframetablecolumn import ZoneCol

def _prepareGrid(self):
    self.cropTop = QSpinBox(self)
    self.cropLeft = QSpinBox(self)
    self.cropRight = QSpinBox(self)
    self.cropBottom = QSpinBox(self)

    self.cropTop.setSingleStep(2)
    self.cropTop.setMinimum(0)
    self.cropTop.valueChanged.connect(self.setCropTop)
    self.cropTop.setFont(self.sbfont)

    self.cropBottom.setSingleStep(2)
    self.cropBottom.setMinimum(0)
    self.cropBottom.valueChanged.connect(self.setCropBottom)
    self.cropBottom.setFont(self.sbfont)


    self.cropLeft.setSingleStep(2)
    self.cropLeft.setMinimum(0)
    self.cropLeft.valueChanged.connect(self.setCropLeft)
    self.cropLeft.setFont(self.sbfont)

    self.cropRight.setSingleStep(2)
    self.cropRight.setMinimum(0)
    self.cropRight.valueChanged.connect(self.setCropRight)
    self.cropRight.setFont(self.sbfont)

    self.scrollArea = QScrollArea(self)
    self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
    self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)

    glayout = QGridLayout()

    tlayout = QHBoxLayout()
    tlayout.addStretch()
    tlayout.addWidget(self.cropTop)
    tlayout.addStretch()

    glayout.addLayout(tlayout, 0, 1)
    glayout.addWidget(self.cropLeft, 1, 0)
    glayout.addWidget(self.scrollArea, 1, 1)
    glayout.addWidget(self.cropRight, 1, 2)

    blayout = QHBoxLayout()
    blayout.addStretch()
    blayout.addWidget(self.cropBottom)
    blayout.addStretch()

    glayout.addLayout(blayout, 2, 1)
    return glayout

class ShadowZone(BaseShadowZone, CropZone):
    pass

class CropDlg(QDialog):
    sbfont = QFont("Dejavu Serif", 8)
    def __init__(self, top, bottom, left, right, prev=None, *args, **kwargs):
        super(CropDlg, self).__init__(*args, **kwargs)
        self.setWindowTitle("Configure Crop")

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        glayout = _prepareGrid(self)
        layout.addLayout(glayout)

        #self.zoomInBtn = QPushButton(self)
        #sublayout.addWidget(self.zoomInBtn)
        #self.zoomInBtn.setIcon(QIcon.fromTheme("zoom-in"))
        #self.zoomInBtn.clicked.connect(self.zoomIn)

        #self.zoomOutBtn = QPushButton(self)
        #sublayout.addWidget(self.zoomOutBtn)
        #self.zoomOutBtn.setIcon(QIcon.fromTheme("zoom-out"))
        #self.zoomOutBtn.clicked.connect(self.zoomOut)

        #self.zoomOrigBtn = QPushButton(self)
        #sublayout.addWidget(self.zoomOrigBtn)
        #self.zoomOrigBtn.setIcon(QIcon.fromTheme("zoom-orig"))
        #self.zoomOrigBtn.clicked.connect(self.zoomOrig)

        #sublayout.addStretch()

        self.slider = Slider(self)
        layout.addWidget(self.slider)

        self.slider.setOrientation(Qt.Horizontal)
        self.slider.valueChanged.connect(self.loadFrame)
        self.slider.setTickInterval(1)

        ###

        sublayout = QHBoxLayout()
        layout.addLayout(sublayout)

        sublayout.addStretch()

        self.okayBtn = QPushButton("&OK", self)
        sublayout.addWidget(self.okayBtn)

        self.closeBtn = QPushButton("&Cancel", self)
        sublayout.addWidget(self.closeBtn)

        self.okayBtn.setDefault(True)
        self.okayBtn.clicked.connect(self.applyAndClose)
        self.closeBtn.clicked.connect(self.close)

        if prev is not None:
            self.load(prev)

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
                    J = j*hzoom
                    painter.drawLine(x0 + J, y0, x0 + J, y0 + H)

                for j in range(0, h + 1):
                    J = j*vzoom
                    painter.drawLine(x0, y0 + J, x0 + W, y0 + J)

        pen = QPen(Qt.red, 1)
        painter.setPen(pen)

        j = k = int(zoom < 8)

        if self._mode == 1:
            painter.drawLine(x0 + self.shadow.cropleft*zoom - j, y0, x0 + self.shadow.cropleft*zoom - j, y0 + H)
            painter.drawLine(x0 + W - self.shadow.cropright*zoom , y0, x0 + W - self.shadow.cropright*zoom , y0 + H)
            painter.drawLine(x0, y0 + self.shadow.croptop*zoom - k, x0 + W, y0 + self.shadow.croptop*zoom - k)
            painter.drawLine(x0, y0 + H - self.shadow.cropbottom*zoom, x0 + W, y0 + H - self.shadow.cropbottom*zoom)

    #def zoomIn(self):
        #zoom = self.imageView.hzoom
        #newzoom = max(min(zoom*sqrt(2), 16), 0.125)
        #self.imageView.setZoom(newzoom, newzoom)

    #def zoomOut(self):
        #zoom = self.imageView.hzoom
        #newzoom = max(min(zoom/sqrt(2), 16), 0.125)
        #self.imageView.setZoom(newzoom, newzoom)

    #def zoomOrig(self):
        #self.imageView.setZoom(1, 1)

    def isModified(self):
        self.modified = True

    def notModified(self):
        self.modified = False

    @pyqtSlot(int)
    def setCropTop(self, croptop):
        self.imageView.croptop = croptop

        if self.prev is not None:
            self.cropBottom.setMaximum(self.prev.height - croptop - 2)

        self.imageView.repaint()
        self.isModified()

    @pyqtSlot(int)
    def setCropBottom(self, cropbottom):
        self.imageView.cropbottom = cropbottom

        if self.prev is not None:
            self.cropTop.setMaximum(self.prev.height - cropbottom - 2)

        self.imageView.repaint()
        self.isModified()

    @pyqtSlot(int)
    def setCropLeft(self, cropleft):
        self.imageView.cropleft = cropleft

        if self.prev is not None:
            self.cropRight.setMaximum(self.prev.width - cropleft - 2)

        self.imageView.repaint()
        self.isModified()

    @pyqtSlot(int)
    def setCropRight(self, cropright):
        self.imageView.cropright = cropright

        if self.prev is not None:
            self.cropLeft.setMaximum(self.prev.width - cropright - 2)

        self.imageView.repaint()
        self.isModified()

    @pyqtSlot(bool)
    def setCrop(self, modified):
        self.imageView.setCrop(self.cropTop.value(), self.cropBottom.value(), self.cropLeft.value(), self.cropRight.value())

        if  self.prev is not None:
            self.cropTop.setMaximum(self.prev.height - self.cropBottom.value() - 2)
            self.cropBottom.setMaximum(self.prev.height - self.cropTop.value() - 2)
            self.cropRight.setMaximum(self.prev.width - self.cropLeft.value() - 2)
            self.cropLeft.setMaximum(self.prev.width - self.cropRight.value() - 2)

        self.imageView.repaint()

        if modified:
            self.isModified()

    def load(self, prev):
        self.prev = prev

        aspectratio = self.prev.width/self.prev.height

        w, h = min([(self.prev.width, self.prev.height), (960, int(960/aspectratio)), (int(640*aspectratio), 640)])

        self.slider.setMinimum(0)
        self.slider.setMaximum(prev.framecount - 1)

        self.loadFrame()
        self.imageView.repaint()
        self.setCrop(False)
        self.notModified()
        self.cropTop.setFocus()

    @pyqtSlot()
    def loadFrame(self):
        n = self.slider.value()
        frame = next(self.prev.readFrames(n))
        im = frame.to_image()
        self.imageView.setFrame(im)

    @pyqtSlot()
    def show(self):
        if self.parent() is not None:
            self.parent().setDisabled(True)
        QDialog.show(self)

    @pyqtSlot()
    def applyAndClose(self):
        self.done(1)

    @pyqtSlot()
    def close(self):
        if self.parent() is not None:
            self.parent().setEnabled(True)
        QDialog.close(self)

class CropZoneDlg(ZoneDlg):
    shadowclass = ShadowZone
    sbfont = QFont("Dejavu Serif", 8)

    def _prepare(self):
        layout = QVBoxLayout()
        self.setLayout(layout)

        glayout = _prepareGrid(self)
        layout.addLayout(glayout)
        
        self._prepareImageView(self.scrollArea)
        self.imageView.setPaintHook(self._paintHook)
        self.imageView.setSar(1)

        self._prepareStdZoneControls(layout)

        self._prepareDlgButtons(layout)

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
                    J = j*hzoom
                    painter.drawLine(x0 + J, y0, x0 + J, y0 + H)

                for j in range(0, h + 1):
                    J = j*vzoom
                    painter.drawLine(x0, y0 + J, x0 + W, y0 + J)

        pen = QPen(Qt.red, 1)
        painter.setPen(pen)

        j = k = int(zoom < 8)

        if self._mode == 1:
            painter.drawLine(x0 + self.shadow.cropleft*zoom - j, y0, x0 + self.shadow.cropleft*zoom - j, y0 + H)
            painter.drawLine(x0 + W - self.shadow.cropright*zoom , y0, x0 + W - self.shadow.cropright*zoom , y0 + H)
            painter.drawLine(x0, y0 + self.shadow.croptop*zoom - k, x0 + W, y0 + self.shadow.croptop*zoom - k)
            painter.drawLine(x0, y0 + H - self.shadow.cropbottom*zoom, x0 + W, y0 + H - self.shadow.cropbottom*zoom)

    def zoomIn(self):
        zoom = self.imageView.hzoom
        newzoom = max(min(zoom*sqrt(2), 16), 0.125)
        #print(zoom, newzoom)
        self.imageView.setZoom(newzoom, newzoom)

    def zoomOut(self):
        zoom = self.imageView.hzoom
        newzoom = max(min(zoom/sqrt(2), 16), 0.125)
        #print(zoom, newzoom)
        self.imageView.setZoom(newzoom, newzoom)

    def zoomOrig(self):
        self.imageView.setZoom(1, 1)

        #w, h = min()

    def isModified(self):
        self.modified = True
        self.closeBtn.setText("&Cancel")
        self.okayBtn.setDisabled(False)
        self.applyBtn.setDisabled(False)

    def notModified(self):
        self.modified = False
        self.closeBtn.setText("&Close")
        self.okayBtn.setDisabled(True)
        self.applyBtn.setDisabled(True)

    @pyqtSlot(int)
    def setCropTop(self, croptop):
        if self.zone is not None and self.zone.parent.prev is not None:
            self.cropBottom.setMaximum(self.zone.parent.prev.height - croptop - 2)

        self.shadow.croptop = croptop

        if self._mode == 2:
            self.loadFrame()

        else:
            self.imageView.repaint()

        self.isModified()

    @pyqtSlot(int)
    def setCropBottom(self, cropbottom):
        if self.zone is not None and self.zone.parent.prev is not None:
            self.cropTop.setMaximum(self.zone.parent.prev.height - cropbottom - 2)

        self.shadow.cropbottom = cropbottom

        if self._mode == 2:
            self.loadFrame()

        else:
            self.imageView.repaint()

        self.isModified()

    @pyqtSlot(int)
    def setCropLeft(self, cropleft):
        if self.zone is not None and self.zone.parent.prev is not None:
            self.cropRight.setMaximum(self.zone.parent.prev.width - cropleft - 2)

        self.shadow.cropleft = cropleft

        if self._mode == 2:
            self.loadFrame()

        else:
            self.imageView.repaint()

        self.isModified()

    @pyqtSlot(int)
    def setCropRight(self, cropright):
        if self.zone is not None and self.zone.parent.prev is not None:
            self.cropLeft.setMaximum(self.zone.parent.prev.width - cropright - 2)

        self.shadow.cropright = cropright

        if self._mode == 2:
            self.loadFrame()

        else:
            self.imageView.repaint()

        self.isModified()

    @pyqtSlot(bool)
    def setCrop(self, modified):
        if self.zone is not None and self.zone.parent.prev is not None:
            self.cropTop.setMaximum(self.zone.parent.prev.height - self.cropBottom.value() - 2)
            self.cropBottom.setMaximum(self.zone.parent.prev.height - self.cropTop.value() - 2)
            self.cropRight.setMaximum(self.zone.parent.prev.width - self.cropLeft.value() - 2)
            self.cropLeft.setMaximum(self.zone.parent.prev.width - self.cropRight.value() - 2)

        self.imageView.repaint()

        if modified:
            self.isModified()

    def _loadZone(self):
        zone = self.zone

        self.cropTop.blockSignals(True)
        if zone.croptop is not None:
            self.cropTop.setValue(zone.croptop)
            self.cropBottom.setMaximum(zone.parent.prev.height - zone.croptop - 2)

        else:
            self.cropTop.setValue(0)
            self.cropBottom.setMaximum(zone.parent.prev.height - 2)

        self.cropTop.blockSignals(False)

        self.cropBottom.blockSignals(True)

        if zone.cropbottom is not None:
            self.cropBottom.setValue(zone.cropbottom)
            self.cropTop.setMaximum(zone.parent.prev.height - zone.cropbottom - 2)

        else:
            self.cropBottom.setValue(0)
            self.cropTop.setMaximum(zone.parent.prev.height - 2)

        self.cropBottom.blockSignals(False)

        self.cropLeft.blockSignals(True)

        if zone.cropleft is not None:
            self.cropRight.setMaximum(zone.parent.prev.width - zone.cropleft - 2)
            self.cropLeft.setValue(zone.cropleft)

        else:
            self.cropRight.setMaximum(zone.parent.prev.width - 2)
            self.cropLeft.setValue(0)

        self.cropLeft.blockSignals(False)

        self.cropRight.blockSignals(True)

        if zone.cropright is not None:
            self.cropLeft.setMaximum(zone.parent.prev.width - zone.cropright - 2)
            self.cropRight.setValue(zone.cropright)

        else:
            self.cropLeft.setMaximum(zone.parent.prev.width - 2)
            self.cropRight.setValue(0)

        self.cropRight.blockSignals(False)

        aspectratio = zone.parent.prev.width/zone.parent.prev.height

        w, h = min([(zone.parent.prev.width, zone.parent.prev.height), (960, int(960/aspectratio)), (int(640*aspectratio), 640)])

        self.imageView.setFixedSize(w, h)
        self.cropTop.setFocus()

class ResizeDlg(QDialog):
    sbfont = QFont("Dejavu Serif", 8)
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("Configure Resize")
        self.widthLabel = QLabel("Width:")
        self.width = QSpinBox()
        self.width.setMinimum(96)
        self.width.setMaximum(4*1920)
        self.widthLabel.setFont(self.sbfont)
        self.width.setFont(self.sbfont)
        self.width.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        self.heightLabel = QLabel("Height:")
        self.height = QSpinBox()
        self.height.setMinimum(64)
        self.height.setMaximum(4*1080)
        self.heightLabel.setFont(self.sbfont)
        self.height.setFont(self.sbfont)
        self.height.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        regex = QRegExp(r"^(\d+(?:\.\d+)?|\.\d+|\d+/\d+)$")
        validator = QRegExpValidator(regex)

        self.sarLabel = QLabel("SAR:")
        self.sarLabel.setFont(self.sbfont)

        self.sar = QLineEdit()
        self.sar.setText("1")
        self.sar.setFont(self.sbfont)
        self.sar.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sar.setValidator(validator)

        gridlayout = QGridLayout()
        gridlayout.addWidget(self.widthLabel, 0, 0)
        gridlayout.addWidget(self.width, 0, 1)
        gridlayout.addWidget(self.heightLabel, 1, 0)
        gridlayout.addWidget(self.height, 1, 1)
        gridlayout.addWidget(self.sarLabel, 2, 0)
        gridlayout.addWidget(self.sar, 2, 1)

        gridlayout.setRowMinimumHeight(0, 32)
        gridlayout.setRowMinimumHeight(1, 32)
        gridlayout.setRowMinimumHeight(2, 32)
        gridlayout.setHorizontalSpacing(4)

        gridlayout.setColumnMinimumWidth(1, 96)

        self.okayBtn = QPushButton("&OK")
        self.okayBtn.setDefault(True)
        self.okayBtn.setFont(self.sbfont)
        self.okayBtn.clicked.connect(self.applyAndClose)
        self.closeBtn = QPushButton("&Cancel")
        self.closeBtn.clicked.connect(self.close)
        self.closeBtn.setFont(self.sbfont)

        btnlayout = QHBoxLayout()
        btnlayout.setSpacing(4)
        btnlayout.addWidget(self.okayBtn)
        btnlayout.addWidget(self.closeBtn)

        layout = QVBoxLayout()
        layout.setSpacing(4)

        layout.addLayout(gridlayout)
        layout.addLayout(btnlayout)

        self.setLayout(layout)

        self.setFixedHeight(32 + 2*(32 + 4) + 32)
        self.setFixedWidth(140)

    def applyAndClose(self):
        self.done(1)
        self.close()

class CropResizeCol(ZoneCol):
    bgcolor = QColor(255, 128, 64)
    bgcoloralt = QColor(255, 255, 255)
    fgcolor = QColor(0, 0, 0)
    fgcoloralt = QColor(160, 160, 160)
    headerdisplay = "Crop"
    width = 128

    def display(self, index, obj):
        J, zone = self.filter.zoneAt(obj)
        return "{J} ({zone.croptop}, {zone.cropbottom}, {zone.cropleft}, {zone.cropright})".format(J=J, zone=zone)

    def createContextMenu(self, table, index, obj):
        menu = ZoneCol.createContextMenu(self, table, index, obj)
        menu.addSeparator()

        if isinstance(self.filter.parent, FilterChain):
            for scenes in self.filter.parent:
                if isinstance(scenes, Scenes):
                    zoneatscenes = QAction("Create zones from scenes", table, triggered=partial(self.zoneAtScenes, table=table, scenes=scenes))
                    break

            else:
                zoneatscenes = QAction("Create zones from scenes", table, triggered=partial(self.zoneAtScenes, table=table, scenes=None))
                zoneatscenes.setEnabled(False)

        else:
            zoneatscenes = QAction("Create zones from scenes", table, triggered=partial(self.zoneAtScenes, table=table, scenes=None))
            zoneatscenes.setEnabled(False)

        menu.addAction(zoneatscenes)

        configure = QAction("Configure zone...", table, triggered=partial(self.createDlg, table=table, index=index))
        menu.addAction(configure)
        return menu

    def createDlg(self, table, index):
        J, zone = self.filter.zoneAt(index.row())
        dlg = CropZoneDlg(zone, table)
        dlg.settingsChanged.connect(table.contentsModified)
        dlg.slider.setValue(self.filter.cumulativeIndexMap[index.row()])
        dlg.exec_()

    def zoneAtScenes(self, table, scenes):
        for scene in scenes:
            J, p = self.filter.zoneAt(scene.src_start)

            if p.src_start == scene.src_start:
                continue

            self.filter.insertZoneAt(scene.src_start, croptop=p.croptop, cropbottom=p.cropbottom, cropleft=p.cropleft, cropright=p.cropright)

        table.contentsModified.emit()
