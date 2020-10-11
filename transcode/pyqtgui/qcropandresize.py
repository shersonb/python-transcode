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

class ShadowZone(BaseShadowZone, CropZone):
    pass

#class CropPreview(movie.qframeview.FrameLabel):
    #def __init__(self, *args, **kwargs):
        #super(CropPreview, self).__init__(*args, **kwargs)
        ##movie.qframeview.FrameLabel.__init__(self, *args, **kwargs)
        #self.cropleft = 0
        #self.cropright = 0
        #self.croptop = 0
        #self.cropbottom = 0

    #@pyqtSlot(int, int)
    #def setZoom(self, hzoom, vzoom):
        #self.hzoom = hzoom
        #self.vzoom = vzoom
        #pixmap = self.pixmap()
        #if pixmap is not None:
            #self.setFixedWidth(self.hzoom*pixmap.width() + 8)
            #self.setFixedHeight(self.vzoom*pixmap.height() + 8)

    #def setFrame(self, frame):
        #if frame.width*frame.height == 0:
            #self.setPixmap(QPixmap())
        #else:
            #self.setFixedWidth(self.hzoom*frame.width + 8)
            #self.setFixedHeight(self.vzoom*frame.height + 8)
            #self.setPixmap(frame.toqpixmap())

    #def setCrop(self, top, bottom, left, right):
        #self.croptop = top
        #self.cropbottom = bottom
        #self.cropleft = left
        #self.cropright = right

    #def _paintHook(self, widget, event, painter):
        #w, h = widget.pixmap().width(), widget.pixmap().height()
        #W = widget.width()
        #H = widget.height()

        #hzoom = (W - 8)/w
        #vzoom = (H - 8)/h

        #if widget.pixmap() is not None:
            #r = widget.rect()
            #r.adjust(4, 4, -4, -4)

            #if hzoom >= 8 and vzoom >= 8:
                #pen = QPen(Qt.gray, 1)
                #painter.setPen(pen)

                #for j in range(0, w + 1):
                    #J = j*hzoom
                    #painter.drawLine(4 + J, 4, 4 + J, 4 + H)

                #for j in range(0, h + 1):
                    #J = j*vzoom
                    #painter.drawLine(4, 4 + J, 4 + W, 4 + J)

        #pen = QPen(Qt.red, 1)
        #painter.setPen(pen)

        #j = int(hzoom < 8)
        #k = int(vzoom < 8)

        #painter.drawLine(4 + self.shadow.cropleft*hzoom - j, 4, 4 + self.shadow.cropleft*hzoom - j, 4 + H)
        #painter.drawLine(4 + W - self.shadow.cropright*hzoom , 4, 4 + W - self.shadow.cropright*hzoom , 4 + H)
        #painter.drawLine(4, 4 + self.shadow.croptop*vzoom - k, 4 + W, 4 + self.shadow.croptop*vzoom - k)
        #painter.drawLine(4, 4 + H - self.shadow.cropbottomvzoom, 4 + W, 4 + H - self.shadow.cropbottom*vzoom)

#class Slider(QSlider):
    #def __init__(self, *args, **kwargs):
        #super(Slider, self).__init__(*args, **kwargs)
        #self._scrollWheelValue = 32

    #def mousePressEvent(self, event):
        #opt = QStyleOptionSlider()
        #self.initStyleOption(opt)
        #sr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
        #if sr.contains(event.pos()):
            #event.accept()
            #QSlider.mousePressEvent(self, event)
        #elif event.button() == Qt.LeftButton:
            #ti = self.tickInterval() if self.tickInterval() > 0 else 1
            #if self.orientation() == Qt.Horizontal:
                #W = self.width()
                #w = sr.width()
                #x = event.x()
                ##print((self.width(), w))
                ##if self.tickInterval() > 0:
                    ##value = self.minimum() + int(float(self.maximum() - self.minimum())*(event.x() - w/2)/(self.width() - w)/self.tickInterval() + 0.5)*self.tickInterval()
                ##else:
                    ##value = self.minimum() + int(float(self.maximum() - self.minimum())*(event.x() - w/2)/(self.width() - w) + 0.5)
            #elif self.orientation() == Qt.Vertical:
                #W = self.height()
                #w = sr.height()
                #x = event.y()
                ##value = self.minimum() + self.tickInterval()/2.0 + float(self.maximum() - self.minimum())*(event.y() - h/2)/(self.height() - h)
            #value = self.minimum() + int(float(self.maximum() - self.minimum())*(x - w/2)/(W - w)/ti + 0.5)*ti

            #if self.invertedAppearance():
                #self.setValue(self.maximum() + self.minimum() - value)
            #else:
                #self.setValue(value)
            #event.accept()
    ##def wheelEvent(self, event):
        ###print event.angleDelta().y()
        ##self.setValue(self.value() + event.angleDelta().y()/125)
        ##QSlider.wheelEvent(self, event)
    #def wheelEvent(self, event):
        #iv = self.tickInterval() if self.tickInterval() else 1
        #x = self.value()
        #self._scrollWheelValue += event.angleDelta().y()

        #dx, self._scrollWheelValue = divmod(self._scrollWheelValue, 64)
        #if dx:
            #self.setValue(x + dx)
            #event.accept()

class CropDlg(QDialog):
    sbfont = QFont("Dejavu Serif", 8)
    def __init__(self, top, bottom, left, right, prev=None, *args, **kwargs):
        super(CropDlg, self).__init__(*args, **kwargs)
        #QDialog.__init__(self, *args, **kwargs)
        self.setWindowTitle("Configure Crop")

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        sublayout = QHBoxLayout()
        layout.addLayout(sublayout)

        sublayout.addStretch()
        self.cropTop = QSpinBox(self)
        sublayout.addWidget(self.cropTop)
        sublayout.addStretch()

        sublayout = QHBoxLayout()
        layout.addLayout(sublayout)

        sublayout2 = QVBoxLayout()
        sublayout.addLayout(sublayout2)
        sublayout2.addStretch()
        self.cropLeft = QSpinBox(self)
        sublayout2.addWidget(self.cropLeft)
        sublayout2.addStretch()

        self.scrollArea = QScrollArea(self)
        sublayout.addWidget(self.scrollArea)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.imageView = CropPreview(self.scrollArea)
        self.scrollArea.setWidget(self.imageView)
        self.imageView.setZoom(1, 1)

        sublayout2 = QVBoxLayout()
        sublayout.addLayout(sublayout2)
        sublayout2.addStretch()
        self.cropRight = QSpinBox(self)
        sublayout2.addWidget(self.cropRight)
        sublayout2.addStretch()

        sublayout = QHBoxLayout()
        layout.addLayout(sublayout)
        sublayout.addStretch()
        self.cropBottom = QSpinBox(self)
        sublayout.addWidget(self.cropBottom)
        sublayout.addStretch()

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

        self.prev = None
        self.cropTop.setValue(top)
        self.cropBottom.setValue(bottom)
        self.cropLeft.setValue(left)
        self.cropRight.setValue(right)

        sublayout = QHBoxLayout()
        layout.addLayout(sublayout)
        sublayout.addStretch()

        self.zoomInBtn = QPushButton(self)
        sublayout.addWidget(self.zoomInBtn)
        self.zoomInBtn.setIcon(QIcon.fromTheme("zoom-in"))
        self.zoomInBtn.clicked.connect(self.zoomIn)

        self.zoomOutBtn = QPushButton(self)
        sublayout.addWidget(self.zoomOutBtn)
        self.zoomOutBtn.setIcon(QIcon.fromTheme("zoom-out"))
        self.zoomOutBtn.clicked.connect(self.zoomOut)

        self.zoomOrigBtn = QPushButton(self)
        sublayout.addWidget(self.zoomOrigBtn)
        self.zoomOrigBtn.setIcon(QIcon.fromTheme("zoom-orig"))
        self.zoomOrigBtn.clicked.connect(self.zoomOrig)

        sublayout.addStretch()

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
        #self.closeBtn.setText("&Cancel")
        #self.okayBtn.setDisabled(False)
        #self.applyBtn.setDisabled(False)

    def notModified(self):
        self.modified = False
        #self.closeBtn.setText("&Close")
        #self.okayBtn.setDisabled(True)
        #self.applyBtn.setDisabled(True)

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
        self.done(True)

    #@pyqtSlot()
    #def apply(self):
        #self.zone.cropleft = self.cropLeft.value()
        #self.zone.cropright = self.cropRight.value()
        #self.zone.croptop = self.cropTop.value()
        #self.zone.cropbottom = self.cropBottom.value()
        #self.zone.parent.width = self.width.value()
        #self.zone.parent.height = self.height.value()
        #sar = self.sar.text()
        #if regex.match(r"^\d+/\d+$", sar):
            #self.zone.parent.sar = QQ(sar)
        #elif regex.match(r"^\d+$", sar):
            #self.zone.parent.sar = int(sar)
        #else:
            #self.zone.parent.sar = float(sar)
        ##print("**", type(self.parent()))
        #if isinstance(self.parent(), qtable.TableView):
            ##print("##")
            #self.parent().contentsUpdated.emit()
        #self.closeBtn.setText("&Close")
        #self.okayBtn.setDisabled(True)
        #self.applyBtn.setDisabled(True)

    @pyqtSlot()
    def close(self):
        if self.parent() is not None:
            self.parent().setEnabled(True)
        QDialog.close(self)

class CropZoneDlg(ZoneDlg):
    shadowclass = ShadowZone
    sbfont = QFont("Dejavu Serif", 8)
    def b__init__(self, zone=None, *args, **kwargs):
        super(CropZoneDlg, self).__init__(*args, **kwargs)
        #QDialog.__init__(self, *args, **kwargs)
        self.setWindowTitle("Configure Crop Zone")

        layout = QVBoxLayout(self)
        self.setLayout(layout)

        sublayout = QHBoxLayout()
        layout.addLayout(sublayout)

        sublayout.addStretch()
        self.cropTop = QSpinBox(self)
        sublayout.addWidget(self.cropTop)
        sublayout.addStretch()

        sublayout = QHBoxLayout()
        layout.addLayout(sublayout)

        sublayout2 = QVBoxLayout()
        sublayout.addLayout(sublayout2)
        sublayout2.addStretch()
        self.cropLeft = QSpinBox(self)
        sublayout2.addWidget(self.cropLeft)
        sublayout2.addStretch()

        self.scrollArea = QScrollArea(self)
        sublayout.addWidget(self.scrollArea)
        self.scrollArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.imageView = CropPreview(self.scrollArea)
        self.scrollArea.setWidget(self.imageView)
        self.imageView.setZoom(1, 1)

        sublayout2 = QVBoxLayout()
        sublayout.addLayout(sublayout2)
        sublayout2.addStretch()
        self.cropRight = QSpinBox(self)
        sublayout2.addWidget(self.cropRight)
        sublayout2.addStretch()

        sublayout = QHBoxLayout()
        layout.addLayout(sublayout)
        sublayout.addStretch()
        self.cropBottom = QSpinBox(self)
        sublayout.addWidget(self.cropBottom)
        sublayout.addStretch()

        self.zone = zone





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

        sublayout = QHBoxLayout()
        layout.addLayout(sublayout)
        sublayout.addStretch()

        self.zoomInBtn = QPushButton(self)
        sublayout.addWidget(self.zoomInBtn)
        self.zoomInBtn.setIcon(QIcon.fromTheme("zoom-in"))
        self.zoomInBtn.clicked.connect(self.zoomIn)

        self.zoomOutBtn = QPushButton(self)
        sublayout.addWidget(self.zoomOutBtn)
        self.zoomOutBtn.setIcon(QIcon.fromTheme("zoom-out"))
        self.zoomOutBtn.clicked.connect(self.zoomOut)

        self.zoomOrigBtn = QPushButton(self)
        sublayout.addWidget(self.zoomOrigBtn)
        self.zoomOrigBtn.setIcon(QIcon.fromTheme("zoom-orig"))
        self.zoomOrigBtn.clicked.connect(self.zoomOrig)

        sublayout.addStretch()

        self.slider = Slider(self)
        layout.addWidget(self.slider)

        self.slider.setOrientation(Qt.Horizontal)
        self.slider.valueChanged.connect(self.loadFrame)
        self.slider.setTickInterval(1)

        layout2o = QHBoxLayout()
        layout.addLayout(layout2o)

        self.startLabel = QLabel(self)
        layout2o.addWidget(self.startLabel)
        layout2o.addStretch()

        self.currentLabel = QLabel(self)
        layout2o.addWidget(self.currentLabel)
        layout2o.addStretch()

        self.endLabel = QLabel(self)
        layout2o.addWidget(self.endLabel)

        ###

        sublayout = QHBoxLayout()
        layout.addLayout(sublayout)

        self.prevBtn = QPushButton("&Previous Zone", self)
        sublayout.addWidget(self.prevBtn)

        sublayout.addStretch()

        self.toggleZoneBtn = QPushButton("&Insert Scene Here", self)
        self.toggleZoneBtn.clicked.connect(self.toggleZone) # 162523
        sublayout.addWidget(self.toggleZoneBtn)

        sublayout.addStretch()

        self.widthLabel = QLabel("Width:", self)
        sublayout.addWidget(self.widthLabel)

        self.width = QSpinBox(self)
        sublayout.addWidget(self.width)

        self.width.setMaximum(4*1920)
        self.widthLabel.setFont(self.sbfont)
        self.width.setFont(self.sbfont)
        self.width.valueChanged.connect(self.isModified)

        self.heightLabel = QLabel("Height:", self)
        sublayout.addWidget(self.heightLabel)

        self.height = QSpinBox(self)
        sublayout.addWidget(self.height)

        self.height.setMaximum(4*1080)
        self.heightLabel.setFont(self.sbfont)
        self.height.setFont(self.sbfont)
        self.height.valueChanged.connect(self.isModified)

        self.sarLabel = QLabel("SAR:", self)
        sublayout.addWidget(self.sarLabel)
        self.sarLabel.setFont(self.sbfont)

        self.sar = QLineEdit(self)
        sublayout.addWidget(self.sar)
        self.sar.setMaximumWidth(96)

        regex = QRegExp(r"^(\d+(?:\.\d+)?|\.\d+|\d+/\d+)$")
        validator = QRegExpValidator(regex)

        self.sar.setFont(self.sbfont)
        self.sar.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.sar.setValidator(validator)
        self.sar.textChanged.connect(self.isModified)

        sublayout.addStretch()

        self.nextBtn = QPushButton("&Next Zone", self)
        sublayout.addWidget(self.nextBtn)



        self.prevBtn.clicked.connect(self.prevZone)
        self.nextBtn.clicked.connect(self.nextZone)

        sublayout = QHBoxLayout()
        layout.addLayout(sublayout)

        sublayout.addStretch()

        self.okayBtn = QPushButton("&OK", self)
        sublayout.addWidget(self.okayBtn)

        self.applyBtn = QPushButton("&Apply", self)
        sublayout.addWidget(self.applyBtn)

        self.closeBtn = QPushButton("&Cancel", self)
        sublayout.addWidget(self.closeBtn)

        self.okayBtn.setDefault(True)
        self.okayBtn.clicked.connect(self.applyAndClose)
        self.applyBtn.clicked.connect(self.apply)
        self.closeBtn.clicked.connect(self.close)

        if zone is not None:
            self.loadZone(zone)

    def _prepare(self):
        layout = QVBoxLayout(self)
        self.setLayout(layout)

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

        glayout.addWidget(self.cropTop, 0, 1)
        glayout.addWidget(self.cropLeft, 1, 0)
        glayout.addWidget(self.scrollArea, 1, 1)
        glayout.addWidget(self.cropRight, 1, 2)
        glayout.addWidget(self.cropBottom, 2, 1)

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

    def loadZone(self, zone):
        self.zone = zone

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


        #self.width.blockSignals(True)
        #self.width.setValue(zone.parent.width)
        #self.width.blockSignals(False)

        #self.height.blockSignals(True)
        #self.height.setValue(zone.parent.height)
        #self.height.blockSignals(False)

        #self.sar.blockSignals(True)
        #self.sar.setText(str(zone.parent.sar))
        #self.sar.blockSignals(False)

        super().loadZone(zone)

        #self.notModified()
        self.cropTop.setFocus()

    #@pyqtSlot()
    #def prevZone(self):
        #if isinstance(self.parent(), qtable.TableView):
            #self.parent().goto(row=self.zone.prev_zone.src_start)
        #self.loadZone(self.zone.prev_zone)

    #@pyqtSlot()
    #def nextZone(self):
        #if isinstance(self.parent(), qtable.TableView):
            #self.parent().goto(row=self.zone.next_zone.src_start)
        #self.loadZone(self.zone.next_zone)

    #@pyqtSlot()
    #def loadFrame(self):
        #n = self.slider.value()
        #frame = next(self.zone.parent.prev.readFrames(n))
        #im = frame.to_image()
        #self.imageView.setFrame(im)

        #if n > self.zone.prev_start:
            #self.toggleZoneBtn.setText("&Insert Zone Here")
        #else:
            #self.toggleZoneBtn.setText("&Remove Zone Here")
        #self.toggleZoneBtn.setEnabled(n > 0)

        #startpts = self.zone.pts_time[0]
        #m, s = divmod(startpts, 60)
        #m = int(m)
        #h, m = divmod(m, 60)
        #self.startLabel.setText(f"{self.zone.prev_start} ({h:.0f}:{m:02.0f}:{s:06.3f})")

        #try:
            #pts = self.zone.pts_time[n - self.zone.prev_start]
            #m, s = divmod(pts, 60)
            #m = int(m)
            #h, m = divmod(m, 60)
            #self.currentLabel.setText(f"{n} ({h:.0f}:{m:02.0f}:{s:06.3f})")
        #except IndexError:
            #self.currentLabel.setText(f"{n} (-:--:--.---)")

        #endpts = self.zone.pts_time[-1]
        #m, s = divmod(endpts, 60)
        #m = int(m)
        #h, m = divmod(m, 60)
        #N = self.zone.prev_end - 1
        #self.endLabel.setText(f"{N} ({h:.0f}:{m:02.0f}:{s:06.3f})")

    #@pyqtSlot()
    #def toggleZone(self):
        #n = self.slider.value()
        #if isinstance(self.zone.parent.prev, movie.filters.BaseFilter):
            #if n > 0:
                #m = self.zone.parent.prev.backcumulativeIndexMap[n-1]+1
            #else:
                #m = 0
        #else:
            #m = n
        #if n > self.zone.prev_start:
            #J, zone = self.zone.parent.insertZoneAt(int(m))
            #if isinstance(self.parent(), qtable.TableView):
                #self.parent().setRowHidden(m, False)
                #self.parent().goto(row=m)
                #self.parent().contentsUpdated.emit()
            #self.loadZone(zone)
        #else:
            #prevzone = self.zone.prev_zone
            #self.zone.parent.removeZoneAt(m)
            #self.loadZone(prevzone)
            #self.slider.setValue(n)
            #if isinstance(self.parent(), qtable.TableView):
                #self.parent().contentsUpdated.emit()

    #@pyqtSlot()
    #def show(self):
        #if self.parent() is not None:
            #self.parent().setDisabled(True)
        #QDialog.show(self)

    #@pyqtSlot()
    #def applyAndClose(self):
        #self.apply()
        #self.close()

    #@pyqtSlot()
    #def apply(self):
        #self.zone.cropleft = self.cropLeft.value()
        #self.zone.cropright = self.cropRight.value()
        #self.zone.croptop = self.cropTop.value()
        #self.zone.cropbottom = self.cropBottom.value()
        #self.zone.parent.width = self.width.value()
        #self.zone.parent.height = self.height.value()
        #sar = self.sar.text()
        #if regex.match(r"^\d+/\d+$", sar):
            #self.zone.parent.sar = QQ(sar)
        #elif regex.match(r"^\d+$", sar):
            #self.zone.parent.sar = int(sar)
        #else:
            #self.zone.parent.sar = float(sar)
        ##print("**", type(self.parent()))
        #if isinstance(self.parent(), qtable.TableView):
            ##print("##")
            #self.parent().contentsUpdated.emit()
        #self.closeBtn.setText("&Close")
        #self.okayBtn.setDisabled(True)
        #self.applyBtn.setDisabled(True)

    #@pyqtSlot()
    #def close(self):
        #if self.parent() is not None:
            #self.parent().setEnabled(True)
            #current = self.parent().currentIndex()
            #col = self.parent().model().mapToSource(current).column()
            #n = self.slider.value()
            #if isinstance(self.zone.parent.prev, movie.filters.BaseFilter):
                #if n > 0:
                    #m = self.zone.parent.prev.backcumulativeIndexMap[n-1]+1
                #else:
                    #m = 0
            #else:
                #m = n
            #goto = self.parent().model().sourceModel().index(m, col)

            #if isinstance(self.parent().model().filterFunc(), set):
                #self.parent().model().filterFunc().add(m)
                #self.parent().model().invalidateFilter()

            #goto = self.parent().model().mapFromSource(goto)

            #if goto.isValid():
                #self.parent().setCurrentIndex(goto)
                #self.parent().scrollTo(goto, QAbstractItemView.PositionAtCenter)
        #QDialog.close(self)

class ResizeDlg(QDialog):
    sbfont = QFont("Dejavu Serif", 8)
    def __init__(self, *args, **kwargs):
        super(ResizeDlg, self).__init__(*args, **kwargs)
        #QDialog.__init__(self, *args, **kwargs)
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
        dlg.slider.setValue(self.filter.cumulativeIndexMap[index.row()])
        dlg.exec_()

    def zoneAtScenes(self, table, scenes):
        for scene in scenes:
            J, p = self.filter.zoneAt(scene.src_start)

            if p.src_start == scene.src_start:
                continue

            self.filter.insertZoneAt(scene.src_start, croptop=p.croptop, cropbottom=p.cropbottom, cropleft=p.cropleft, cropright=p.cropright)

        table.contentsUpdated.emit()

    #def display(self, index, obj):
        #K, zone = self.filter.zoneAt(index)
        #if zone.transition:
            #return "%d Transition" % K
        #return "{K} ({zone.rmin:.2f}, {zone.rgamma:.2f}, {zone.rmax:.2f}), ({zone.gmin:.2f}, {zone.ggamma:.2f}, {zone.gmax:.2f}), ({zone.bmin:.2f}, {zone.bgamma:.2f}, {zone.bmax:.2f}), {zone.gamma:.2f}".format(K=K, zone=zone)

    #def bgdata(self, index, obj):
        #K, zone = self.filter.zoneAt(index)
        #if index == zone.src_start:
            #return self.bgcolor1
        #return self.bgcolor2

    #def fgdata(self, index, obj):
        #K, zone = self.filter.zoneAt(index)
        #if index == zone.src_start:
            #return self.fgcolor1
        #return self.fgcolor2
