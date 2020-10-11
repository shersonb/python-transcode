#from PyQt5.QtGui import QImage, QPainter, QPalette, QPixmap, QColor, QFont, QBrush, QPen, QStandardItemModel, QIcon, QFontMetrics
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QSlider, QStyleOptionSlider, QStyle)
import time

class Slider(QSlider):
    def __init__(self, *args, **kwargs):
        super(Slider, self).__init__(*args, **kwargs)
        self._scrollWheelValue = 0.5
        self._angleHistory = []
        self.T0 = time.time()

    def mousePressEvent(self, event):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        sr = self.style().subControlRect(QStyle.CC_Slider, opt, QStyle.SC_SliderHandle, self)
        if sr.contains(event.pos()):
            event.accept()
            QSlider.mousePressEvent(self, event)
        elif event.button() == Qt.LeftButton:
            ti = self.tickInterval() or 1
            if self.orientation() == Qt.Horizontal:
                W = self.width()
                w = sr.width()
                x = event.x()

            elif self.orientation() == Qt.Vertical:
                W = self.height()
                w = sr.height()
                x = event.y()

            value = self.minimum() + int(float(self.maximum() - self.minimum())*(x - w/2)/(W - w)/ti + 0.5)*ti

            if self.invertedAppearance():
                self.setValue(self.maximum() + self.minimum() - value)
            else:
                self.setValue(value)
            event.accept()

    def setValue(self, x):
        self._scrollWheelValue = 0.5
        QSlider.setValue(self, x)

    def wheelEvent(self, event):
        T = time.time()
        p = 2
        iv = self.tickInterval() or 1
        x = self.value()
        angle = event.angleDelta().y()/120

        while len(self._angleHistory) and self._angleHistory[0] < (T - 0.25, 0):
            del self._angleHistory[0]

        lastAngleSum = sum([a for t, a in self._angleHistory])
        newAngleSum = lastAngleSum + angle

        delta = (newAngleSum*abs(newAngleSum)**(p - 1) - lastAngleSum*abs(lastAngleSum)**(p - 1))

        self._angleHistory.append((T, angle))

        self._scrollWheelValue += delta

        dn, self._scrollWheelValue = divmod(self._scrollWheelValue, 1)

        if dn:
            QSlider.setValue(self, x + iv*dn)
            event.accept()
