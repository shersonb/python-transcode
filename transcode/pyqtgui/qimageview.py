from PyQt5.QtCore import QDir, Qt, QModelIndex, pyqtSignal, QThread, pyqtSlot, QSize, QRect, QPoint
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
import codecfactory

class QImageView(QWidget):
    mousePressed = pyqtSignal(float, float)
    mouseDoubleClicked = pyqtSignal(float, float)
    imageUpdated = pyqtSignal(QPixmap)

    def __init__(self, sizehint=None, *args, **kwargs):
        super(QImageView, self).__init__(*args, **kwargs)
        p = QSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        p.setHeightForWidth(True)
        self._pixmap = QPixmap()
        self._subpixmap = QPixmap()
        self._subpos = QPoint()
        self.setSizePolicy(p)
        self._sizehint = sizehint
        self._sar = 1
        self._painthook = None
        self.imageUpdated.connect(self.setPixmap)

    def setPixmap(self, pixmap):
        oldimh = self._pixmap.height()
        oldimw = self._pixmap.width()
        imh = pixmap.height()
        imw = pixmap.width()
        self._pixmap = pixmap

        if oldimh != imh or oldimw != imw:
            self.updateGeometry()

        self.repaint()

    def subtitlePixmap(self):
        return self._subpixmap

    def subtitlePos(self):
        return self._subpos

    @pyqtSlot(QPixmap, QPoint)
    def setSubtitlePixmap(self, pixmap, pos):
        self._subpixmap = pixmap
        self._subpos = pos
        self.repaint()

    def clearSubtitle(self):
        self._subpixmap = pixmap
        self._subpos = pos
        self.repaint()

    def setPaintHook(self, hook):
        self._painthook = hook
        self.repaint()

    def sar(self):
        return self._sar

    def setSar(self, value):
        self._sar = value
        self.updateGeometry()

    def pixmap(self):
        return self._pixmap

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

    def paintEvent(self, event):
        painter = QPainter(self)

        painter.setRenderHint(QPainter.Antialiasing)
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

        subpixmap = self.subtitlePixmap()

        if subpixmap:
            subpos = self.subtitlePos()
            (rectx, recty, rectw, recth) = (rect.x(), rect.y(), rect.width(), rect.height())
            (subx, suby) = (subpos.x(), subpos.y())
            (subw, subh) = (subpixmap.width(), subpixmap.height())

            if imw > 0 and imh > 0 and subw > 0 and subh > 0:
                X = rectx + subx*rectw/imw
                Y = recty + suby*recth/imh

                W = subw*rectw/imw
                H = subh*recth/imh
                rect = QRect(QPoint(X, Y), QSize(W, H))

                subpixmap = subpixmap.scaled(W, H, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                painter.drawPixmap(rect, subpixmap)

        if callable(self._painthook):
            try:
                self._painthook(painter)

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
