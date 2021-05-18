from PyQt5.QtWidgets import (QMenu, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
                             QSpinBox, QTimeEdit, QPushButton, QItemDelegate,
                             QWidgetAction, QToolButton)
from PyQt5.QtCore import Qt, QTime, pyqtSignal, QSize
from transcode.pyqtgui.qimageview import QImageView
from transcode.pyqtgui.slider import Slider

from transcode.containers.basereader import Track
from transcode.filters.base import BaseFilter


class FrameSelectWidget(QWidget):
    frameSelectionChanged = pyqtSignal(int, QTime)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMaximumWidth(960)

        layout = QVBoxLayout()
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        self.setLayout(layout)

        self.imageView = QImageView(self)
        layout.addWidget(self.imageView)

        self.slider = Slider(self)
        self.slider.setOrientation(Qt.Horizontal)
        self.slider.valueChanged.connect(self.handleSliderChange)
        self.slider.setTickInterval(1)
        layout.addWidget(self.slider)

        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)

        self.prevLabel = QLabel(self)
        self.currentIndex = QSpinBox(self)
        self.currentIndex.valueChanged.connect(self.handleIndexChange)
        self.currentTime = QTimeEdit(self)
        self.currentTime.setDisplayFormat("H:mm:ss.zzz")
        self.currentTime.timeChanged.connect(self.handleTimeChange)
        self.nextLabel = QLabel(self)

        hlayout.addWidget(self.prevLabel)
        hlayout.addStretch()
        hlayout.addWidget(QLabel("Frame index:", self))
        hlayout.addWidget(self.currentIndex)
        hlayout.addWidget(QLabel("Timestamp:", self))
        hlayout.addWidget(self.currentTime)
        hlayout.addStretch()
        hlayout.addWidget(self.nextLabel)

        hlayout = QHBoxLayout()
        hlayout.setContentsMargins(0, 0, 0, 0)
        hlayout.setSpacing(4)
        layout.addLayout(hlayout)

        self.okayBtn = QPushButton("&OK", self)
        self.cancelBtn = QPushButton("&Cancel", self)

        hlayout.addStretch()
        hlayout.addWidget(self.okayBtn)
        hlayout.addWidget(self.cancelBtn)
        self.setFrameSource(None, None)

    def sizeHint(self):
        widgetHeights = (
            self.slider.height()
            + max([self.okayBtn.height(), self.cancelBtn.height()])
            + max([self.currentIndex.height(), self.currentTime.height()])
        )

        if isinstance(self.filters, BaseFilter):
            w, h = self.filters.width, self.filters.height
            sar = self.filters.sar

        elif isinstance(self.source, (Track, BaseFilter)):
            w, h = self.source.width, self.source.height
            sar = self.source.sar

        else:
            return super().sizeHint()

        dar = w*sar/h
        W, H = min([
            max([(w, h/sar), (w*sar, h)]),
            (960 - 8, (960 - 8)/dar),
            ((720 - 20 - widgetHeights)*dar, 720 - 20 - widgetHeights)
        ])

        return QSize(int(W + 8), int(H + 20 + widgetHeights))

    def setFrameSource(self, source, filters=None):
        self.source = source

        if source is not None:
            self.slider.setMaximum(self.source.framecount - 1)
            self.currentIndex.setMaximum(self.source.framecount - 1)
            self.filters = filters

            if self.filters is not None:
                lastpts = self.filters.pts_time[-1]
                self.slider.setSnapValues(self.filters.keyframes)

            else:
                lastpts = self.source.pts_time[-1]

                if isinstance(self.source, BaseFilter):
                    self.slider.setSnapValues(self.source.keyframes)

                else:
                    self.slider.setSnapValues(None)

            ms = int(lastpts*1000 + 0.5)
            s, ms = divmod(ms, 1000)
            m, s = divmod(s, 60)
            h, m = divmod(m, 60)
            self.currentTime.setMaximumTime(QTime(h, m, s, ms))
            self.slider.setValue(0)
            self._frameChange(0)

        else:
            self.slider.setSnapValues(None)

        self.update()

    def handleIndexChange(self, n):
        self._frameChange(n)

        self.slider.blockSignals(True)
        self.slider.setValue(n)
        self.slider.blockSignals(False)

    def handleSliderChange(self, n):
        self._frameChange(n)

        self.currentIndex.blockSignals(True)
        self.currentIndex.setValue(n)
        self.currentIndex.blockSignals(False)

    def _frameChange(self, n):
        if self.source is not None:
            if self.filters is not None:
                nn = n
                m = -1

                while m < 0 and nn < len(self.filters.indexMap):
                    m = self.filters.indexMap[nn]
                    nn += 1

                try:
                    pts = self.filters.pts_time[m]

                except Exception:
                    pts = None

                try:
                    frame = next(self.filters.iterFrames(
                        m, whence="framenumber"))

                except StopIteration:
                    frame = None

                sar = self.filters.sar

            else:
                try:
                    pts = self.source.pts_time[n]

                except IndexError:
                    pts = None

                try:
                    frame = next(self.source.iterFrames(
                        n, whence="framenumber"))

                except StopIteration:
                    frame = None

                sar = self.source.sar

            if frame is not None:
                im = frame.to_image()
                self.imageView.setFrame(im.toqpixmap())
                self.imageView.setSar(sar)

            if pts is not None:
                ms = int(pts*1000+0.5)
                s, ms = divmod(ms, 1000)
                m, s = divmod(s, 60)
                h, m = divmod(m, 60)

                self.currentTime.blockSignals(True)
                self.currentTime.setTime(QTime(h, m, s, ms))
                self.currentTime.blockSignals(False)

            self.frameSelectionChanged.emit(n, self.currentTime.time())

    def handleTimeChange(self, t):
        if self.source is not None:
            if self.filters is not None:
                pts = t.msecsSinceStartOfDay()/1000
                n = self.filters.frameIndexFromPtsTime(pts, dir="-")

            else:
                pts = t.msecsSinceStartOfDay()/1000
                n = self.source.frameIndexFromPtsTime(pts, dir="-")

            self.slider.blockSignals(True)
            self.slider.setValue(n)
            self.slider.blockSignals(False)

            self.currentIndex.blockSignals(True)
            self.currentIndex.setValue(n)
            self.currentIndex.blockSignals(False)

            self._frameChange(n)


class QFrameSelect(QToolButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setPopupMode(QToolButton.MenuButtonPopup)
        self.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        self.widget = FrameSelectWidget(self)
        self.widget.okayBtn.clicked.connect(self._handleOKClicked)
        self.widget.cancelBtn.clicked.connect(self._handleCancelClicked)

        act = QWidgetAction(self)
        act.setDefaultWidget(self.widget)

        self.menu = QMenu(self)
        self.menu.addAction(act)
        self.setMenu(self.menu)

        self.clicked.connect(self.showMenu)
        self.setFrameSource(None, None)
        self.setFrameSelection((0, 0))

    def showMenu(self):
        n, t = self.frameSelection()
        self.widget.slider.setValue(n)
        super().showMenu()

    def frameSelection(self):
        return self._frameSelection

    def setFrameSelection(self, value):
        n, t = value

        if self.widget.source is not None:
            if self.widget.filters is not None:
                self._frameSelection = (
                    n, int(10**9*self.widget.filters.pts_time[n]))

            else:
                self._frameSelection = (
                    n, int(10**9*self.widget.source.pts_time[n]))

        m, s = divmod(float(t/10**9), 60)
        h, m = divmod(int(m), 60)

        self.setText(f"{h}:{m:02d}:{s:012.9f} ({n})")

    def setFrameSource(self, source, filters=None):
        self.widget.setFrameSource(source, filters)

    def _handleOKClicked(self):
        self.setFrameSelection((self.widget.slider.value(
        ), self.widget.currentTime.time().msecsSinceStartOfDay()*10**6))
        self.menu.close()

    def _handleCancelClicked(self):
        self.menu.close()


class TimeSelectDelegate(QItemDelegate):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSource(None)

    def setSource(self, source):
        self._source = source

    def source(self):
        return self._source

    def createEditor(self, parent, option, index):
        if self.source() is not None:
            editor = QFrameSelect(parent)
            editor.setFrameSource(self.source().source, self.source().filters)
            return editor

    def setEditorData(self, editor, index):
        if self.source() is not None:
            data = index.data(Qt.EditRole)
            editor.setFrameSelection(data)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.frameSelection(), Qt.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
