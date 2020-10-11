from PyQt5.QtCore import Qt, pyqtSignal, pyqtSlot, pyqtSlot, QSize, QRect, QPoint
from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QColor, QFont, QBrush, QPen
from PyQt5.QtWidgets import (QAction, QApplication, QFileDialog, QLabel, QFrame,
        QMainWindow, QMenu, QMessageBox, QGridLayout, QScrollArea, QSizePolicy, QWidget,
        QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, QTableWidget, QTableWidgetItem,
        QAbstractItemView, QHeaderView, QProgressBar, QStatusBar, QTabWidget, QVBoxLayout,
        QHBoxLayout, QComboBox, QSizePolicy, QFileDialog)
from av import VideoFrame
from PIL.Image import Image
from fractions import Fraction as QQ
import av
import sys
import traceback
from ass.line import Dialogue
import regex as re

class QImageView(QWidget):
    mousePressed = pyqtSignal(float, float)
    mouseDoubleClicked = pyqtSignal(float, float)
    #frameUpdated = pyqtSignal(QPixmap)

    def __init__(self, sizehint=None, *args, **kwargs):
        super(QImageView, self).__init__(*args, **kwargs)
        p = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        p.setHeightForWidth(True)

        self._pixmap = QPixmap()
        self._subtitle = None
        self._subpos = QPoint()
        self.setSizePolicy(p)

        self._sizehint = sizehint
        self._sar = 1
        self._painthook = None
        #self.frameUpdated.connect(self.setFrame)
        #self.frameUpdated[QPixmap, str, QPoint].connect(self.setFrameAndTextSub)

    def _setPixmap(self, pixmap):
        oldimh = self._pixmap.height()
        oldimw = self._pixmap.width()
        imh = pixmap.height()
        imw = pixmap.width()
        self._pixmap = pixmap

        if oldimh != imh or oldimw != imw:
            self.updateGeometry()

    def pixmap(self):
        return self._pixmap

    def setFrame(self, pixmap, subtitle=None, subpos=None):
        self._setPixmap(pixmap)
        self._subtitle = subtitle
        self._subpos = subpos
        self.repaint()

    def subtitle(self):
        return self._subtitle

    def subtitlePos(self):
        return self._subpos

    #@pyqtSlot(QPixmap, QPoint)
    #def setSubtitlePixmap(self, pixmap, pos):
        #self._subtitle = pixmap
        #self._subpos = pos
        #self.repaint()

    #def clearSubtitle(self):
        #self._subtitle = pixmap
        #self._subpos = pos
        #self.repaint()

    def setPaintHook(self, hook):
        self._painthook = hook
        self.repaint()

    def sar(self):
        return self._sar

    def setSar(self, value):
        self._sar = value
        self.updateGeometry()

    def sizeHint(self):
        imh = self._pixmap.height()
        imw = self._pixmap.width()
        sar = float(self._sar)

        if sar > 1:
            return QSize(imh*sar, imw)

        elif sar < 1:
            return QSize(imw, imh/sar)

        return QSize(imw, imh)

    def heightForWidth(self, width):
        sar = float(self._sar)
        pixmap = self.pixmap()
        w, h = pixmap.width(), pixmap.height()

        if w*h == 0:
            return width

        return width*h/w/sar

    def mousePressEvent(self, event):
        pos = event.pos()
        x = pos.x()
        y = pos.y()
        sar = float(self._sar)

        pixmap = self.pixmap()
        imw = pixmap.width()
        imh = pixmap.height()

        if imh > 0:
            dar = imw*sar/imh

        else:
            dar = 16/9

        w = self.width()
        h = self.height()

        W, H = min([(w, w/dar), (h*dar, h)])

        if W < w:
            x = x - (w - W)/2

        else:
            y = y - (h - H)/2

        self.mousePressed.emit(imw*x/W, imh*y/H)

    def mouseDoubleClickEvent(self, event):
        pos = event.pos()
        x = pos.x()
        y = pos.y()
        sar = float(self._sar)

        pixmap = self.pixmap()
        imw = pixmap.width()
        imh = pixmap.height()

        if imh > 0:
            dar = imw*sar/imh

        else:
            dar = 16/9

        w = self.width()
        h = self.height()

        W, H = min([(w, w/dar), (h*dar, h)])

        if W < w:
            x = x - (w - W)/2

        else:
            y = y - (h - H)/2

        self.mouseDoubleClicked.emit(imw*x/W, imh*y/H)

    def _paintFrame(self, event, painter):
        pixmap = self.pixmap()
        imw = pixmap.width()
        imh = pixmap.height()
        sar = float(self._sar)

        if imh > 0:
            dar = imw*sar/imh

        else:
            dar = 16/9

        w = self.width()
        h = self.height()
        W, H = min([(w, w/dar), (h*dar, h)])

        if W < w:
            rect = QRect(QPoint((w - W)/2, 0), QSize(W, H))
        else:
            rect = QRect(QPoint(0, (h - H)/2), QSize(W, H))

        if imh and imw:
            pixmap = pixmap.scaled(W, H, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(rect, pixmap)

    def _paintPixmapSubtitle(self, event, painter):
        subtitle = self.subtitle()
        subpos = self.subtitlePos()

        (rectx, recty, rectw, recth) = (rect.x(), rect.y(), rect.width(), rect.height())
        (subx, suby) = (subpos.x(), subpos.y())
        (subw, subh) = (subtitle.width(), subtitle.height())

        if imw > 0 and imh > 0 and subw > 0 and subh > 0:
            X = rectx + subx*rectw/imw
            Y = recty + suby*recth/imh

            W = subw*rectw/imw
            H = subh*recth/imh
            rect = QRect(QPoint(X, Y), QSize(W, H))

            subtitle = subtitle.scaled(W, H, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            painter.drawPixmap(rect, subtitle)

    def _paintSSASubtitle(self, event, painter):
        pass

    def _paintTextSubtitle(self, event, painter):
        pass

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        self._paintFrame(event, painter)

        if isinstance(self.subtitle(), QPixmap):
            self._paintPixmapSubtitle(event, painter)

        elif isinstance(self.subtitle(), Dialogue):
            self._paintSSASubtitle(event, painter)

        elif isinstance(self.subtitle(), str):
            self._paintTextSubtitle(event, painter)

        if callable(self._painthook):
            try:
                self._painthook(self, event, painter)

            except:
                traceback.print_exc(file=sys.stderr)

    def contextMenuEvent(self, event):
        menu = QMenu(self)
        save = QAction("&Save image...", self, triggered=self.saveImage)
        menu.addAction(save)
        menu.exec_(self.mapToGlobal(event.pos()))

    def saveImage(self):
        filters = "Image files (*.jpg *.png)"
        defaultname = "frame.jpg"
        fileName, _ = QFileDialog.getSaveFileName(self, "Save File",
                defaultname, filters)
        if fileName:
            if fileName.upper().endswith(".JPG"):
                self.pixmap().toImage().save(fileName, quality=100)
            else:
                self.pixmap().toImage().save(fileName)
            return True
        return False

class QMultiImageView(QWidget):
    setframes = pyqtSignal(*[QPixmap]*5)
    setsubtitle = pyqtSignal(QPixmap, QPoint)

    def __init__(self, *args, **kwargs):
        super(QMultiImageView, self).__init__(*args, **kwargs)

        self.imthumb1 = QImageView(self)
        self.imthumb2 = QImageView(self)
        self.main = QImageView(self)
        self.imthumb3 = QImageView(self)
        self.imthumb4 = QImageView(self)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.main)
        thumblayout = QHBoxLayout()
        thumblayout.setContentsMargins(0, 0, 0, 0)
        thumblayout.setSpacing(4)
        thumblayout.addWidget(self.imthumb1)
        thumblayout.addWidget(self.imthumb2)
        thumblayout.addStretch()
        thumblayout.addWidget(self.imthumb3)
        thumblayout.addWidget(self.imthumb4)
        layout.addLayout(thumblayout)
        self.setLayout(layout)

        self.imwins = (self.imthumb1, self.imthumb2, self.main, self.imthumb3, self.imthumb4)
        self.framesource = self.subtitlesource = None
        self.setFrameSource(None)
        self.setframes.connect(self.setFrames)
        #self.setsubtitle.connect(self.main.setSubtitlePixmap)

    def setFrameSource(self, framesource):
        self.framesource = framesource

    def setSubtitleSource(self, subtitlesource):
        self.subtitlesource = subtitlesource

    def setFrameOffset(self, n):
        subpos = QPoint()
        subpixmap = QPixmap()

        if self.framesource is not None:
            emptyframe = QPixmap(self.framesource.width, self.framesource.height)
            emptyframe.fill(QColor(255, 255, 255, 0))

            if n == 0:
                frames  = [emptyframe, emptyframe]

            elif n == 1:
                frames  = [emptyframe]

            else:
                frames = []

            try:
                for k, frame in enumerate(
                        self.framesource.iterFrames(
                            n - 2 + len(frames),
                            n + 3,
                            whence="framenumber"
                            ),
                        n - 2 + len(frames)):
                    frames.append(frame.to_image().toqpixmap())

            except:
                print(traceback.format_exc(), file=sys.stderr)

            frames.extend([emptyframe]*(5 - len(frames)))

            # TODO: Reimplement subtitles (both pgssub and ass)
            #if self.subtitlesource is not None and n < self.framesource.framecount:
                #pts_time = float(self.framesource.pts[n]*self.framesource.time_base)
                #idx = self.subtitlesource.index_from_pts(int(pts_time/self.subtitlesource.time_base + 0.5))

                #if pts_time >= self.subtitlesource.pts_time[idx]:
                    #pkt = next(self.subtitlesource.iterPackets(idx))

                    #try:
                        #sub = pgssub.pgspacketcodec.decode(pkt.to_bytes())

                    #except codecfactory.exc.ExcessData:
                        #pass

                    #except codecfactory.exc.UnexpectedEndOfData:
                        #pass

                    #else:
                        #image = sub.image

                        #if image is not None and sub.x is not None and sub.y is not None:
                            #subpixmap = image.toqpixmap()
                            #subpos = QPoint(sub.x, sub.y)

        else:
            emptyframe = QPixmap()
            frames = [emptyframe]*5


        self.setframes.emit(*frames[:5])
        #self.setsubtitle.emit(subpixmap, subpos)

    @pyqtSlot(*[QPixmap]*5)
    def setFrames(self, *pixmaps):
        for pixmap, imwin in zip(pixmaps, self.imwins):
            imwin.setFrame(pixmap)

    def resizeEvent(self, event):
        w = event.size().width()
        self.imthumb1.setFixedWidth(w/5)
        self.imthumb2.setFixedWidth(w/5)
        self.imthumb3.setFixedWidth(w/5)
        self.imthumb4.setFixedWidth(w/5)

    def setSar(self, value):
        self._sar = value

        for imwin in self.imwins:
            imwin.setSar(value)

        self.updateGeometry()

