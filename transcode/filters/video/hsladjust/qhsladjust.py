from PyQt5.QtCore import pyqtSlot, QTime
from PyQt5.QtWidgets import (QLabel, QSpinBox, QDoubleSpinBox,
                             QVBoxLayout, QHBoxLayout, QWidget)

from transcode.pyqtgui.qfilterconfig import QFilterConfig
from transcode.pyqtgui.qframeselect import QFrameSelect
from transcode.pyqtgui.qimageview import QImageView
from . import HSLAdjust


class QHSLAdjDlg(QFilterConfig):
    allowedtypes = ("video",)

    def _createControls(self):
        self.setWindowTitle("Configure Hue/Saturation/Luminosity")

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

        self.imageView = QImageView(self)
        layout.addWidget(self.imageView)

        self.slider = QFrameSelect(self)
        self.slider.frameSelectionChanged.connect(self.loadFrame)
        layout.addWidget(self.slider)

        hueLabel = QLabel("Hue adjustment:", self)
        self.hueSpinBox = QSpinBox(self)
        self.hueSpinBox.setMinimum(-179)
        self.hueSpinBox.setMaximum(180)
        self.hueSpinBox.valueChanged.connect(
            self._handleHueSpinBoxValueChanged)

        satLabel = QLabel("Saturation factor:", self)
        self.satSpinBox = QDoubleSpinBox(self)
        self.satSpinBox.setDecimals(2)
        self.satSpinBox.setSingleStep(0.1)
        self.satSpinBox.setMinimum(0)
        self.satSpinBox.setMaximum(10)
        self.satSpinBox.valueChanged.connect(
            self._handleSatSpinBoxValueChanged)

        lumLabel = QLabel("Luminosity factor:", self)
        self.lumSpinBox = QDoubleSpinBox(self)
        self.lumSpinBox.setDecimals(2)
        self.lumSpinBox.setMinimum(0)
        self.lumSpinBox.setMaximum(10)
        self.lumSpinBox.valueChanged.connect(
            self._handleLumSpinBoxValueChanged)

        hlayout = QHBoxLayout()

        hlayout.addStretch()
        hlayout.addWidget(hueLabel)
        hlayout.addWidget(self.hueSpinBox)

        hlayout.addStretch()
        hlayout.addWidget(satLabel)
        hlayout.addWidget(self.satSpinBox)

        hlayout.addStretch()
        hlayout.addWidget(lumLabel)
        hlayout.addWidget(self.lumSpinBox)

        hlayout.addStretch()

        layout.addLayout(hlayout)

        self._prepareDlgButtons()

    def createNewFilterInstance(self):
        return HSLAdjust()

    def _resetControls(self):
        self.hueSpinBox.blockSignals(True)
        self.hueSpinBox.setValue(self.filtercopy.dh)
        self.hueSpinBox.blockSignals(False)

        self.satSpinBox.blockSignals(True)
        self.satSpinBox.setValue(self.filtercopy.sfactor)
        self.satSpinBox.blockSignals(False)

        self.lumSpinBox.blockSignals(True)
        self.lumSpinBox.setValue(self.filtercopy.lgamma)
        self.lumSpinBox.blockSignals(False)

        if self.filtercopy.prev is not None:
            self.slider.setPtsTimeArray(self.filtercopy.prev.pts_time)
            self.loadFrame(self.slider.slider.value(), QTime())

    def _handleHueSpinBoxValueChanged(self, value):
        self.filtercopy.dh = value
        self.isModified()
        self.loadFrame(self.slider.slider.value(), None)

    def _handleSatSpinBoxValueChanged(self, value):
        self.filtercopy.sfactor = value
        self.isModified()
        self.loadFrame(self.slider.slider.value(), None)

    def _handleLumSpinBoxValueChanged(self, value):
        self.filtercopy.sfactor = value
        self.isModified()
        self.loadFrame(self.slider.slider.value(), None)

    @pyqtSlot(int, QTime)
    def loadFrame(self, n, t):
        if self.filtercopy.prev is not None:
            frame = next(self.filtercopy.iterFrames(n, whence="framenumber"))
            im = frame.to_image()
            pixmap = im.convert("RGBA").toqpixmap()
            self.imageView.setFrame(pixmap)

    def _prevChanged(self, source):
        self.slider.setPtsTimeArray(source.pts_time)
        self.loadFrame(self.slider.slider.value(),
                       self.slider.currentTime.time())
