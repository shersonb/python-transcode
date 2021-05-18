from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QSlider, QStyleOptionSlider, QStyle)
import time


class Slider(QSlider):
    def __init__(self, *args, **kwargs):
        super(Slider, self).__init__(*args, **kwargs)
        self._scrollWheelValue = 0.5
        self._angleHistory = []
        self._sliderGrabbed = False
        self._snapValues = None
        self.T0 = time.time()

    def setSnapValues(self, value):
        if value is not None:
            self._snapValues = sorted(value)

        else:
            self._snapValues = None

    def _valueFromMouseLocation(self, event):
        opt = QStyleOptionSlider()
        sr = self.style().subControlRect(QStyle.CC_Slider, opt,
                                         QStyle.SC_SliderHandle, self)
        ti = self.tickInterval() or 1

        if self.orientation() == Qt.Horizontal:
            W = self.width()
            w = sr.width()
            x = event.x()

        elif self.orientation() == Qt.Vertical:
            W = self.height()
            w = sr.height()
            x = event.y()

        return (self.minimum()
                + int(float(self.maximum() - self.minimum())
                      * (x - w/2)/(W - w)/ti + 0.5)*ti)

    def mousePressEvent(self, event):
        opt = QStyleOptionSlider()
        self.initStyleOption(opt)
        sr = self.style().subControlRect(QStyle.CC_Slider, opt,
                                         QStyle.SC_SliderHandle, self)

        if sr.contains(event.pos()):
            event.accept()
            self._sliderGrabbed = True
            super().mousePressEvent(event)

        elif event.button() == Qt.LeftButton:
            value = self._valueFromMouseLocation(event)

            if self.invertedAppearance():
                self.setValue(self.maximum() + self.minimum() - value)

            else:
                self.setValue(value)

            event.accept()

    def mouseMoveEvent(self, event):
        if event.modifiers() & Qt.ShiftModifier and self._snapValues:
            value = self._valueFromMouseLocation(event)
            less = [n for n in self._snapValues if n <= value]
            more = [n for n in self._snapValues if n >= value]

            if len(less) == 0:
                value = min(more)

            elif len(more) == 0:
                value = max(less)

            else:
                value = min([min(more), max(less)],
                            key=lambda x: abs(value - x))

            if self.invertedAppearance():
                self.setValue(self.maximum() + self.minimum() - value)

            else:
                self.setValue(value)

            return

        super().mouseMoveEvent(event)

    def setValue(self, x):
        self._scrollWheelValue = 0.5
        super().setValue(x)

    def wheelEvent(self, event):
        T = time.time()
        p = 2
        angle = event.angleDelta().y()/120

        while (len(self._angleHistory)
               and self._angleHistory[0] < (T - 0.25, 0)):
            del self._angleHistory[0]

        lastAngleSum = sum([a for t, a in self._angleHistory])
        newAngleSum = lastAngleSum + angle

        delta = (newAngleSum*abs(newAngleSum)**(p - 1) -
                 lastAngleSum*abs(lastAngleSum)**(p - 1))

        self._angleHistory.append((T, angle))

        self._scrollWheelValue += delta

        dn, self._scrollWheelValue = divmod(self._scrollWheelValue, 1)

        if dn:
            x = self.value()

            if event.modifiers() & Qt.ShiftModifier and self._snapValues:
                if dn < 0:
                    snapIndex = len([n for n in self._snapValues if n < x])

                else:
                    snapIndex = len(
                        [n for n in self._snapValues if n <= x]) - 1

                newSnapIndex = max(
                    0, min(snapIndex + int(dn), len(self._snapValues) - 1))
                value = self._snapValues[newSnapIndex]
                super().setValue(value)

            else:
                iv = self.tickInterval() or 1
                super().setValue(x + iv*dn)

            event.accept()
