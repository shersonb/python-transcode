from PyQt5.QtWidgets import (QLabel, QGridLayout, QVBoxLayout, QHBoxLayout,
                             QWidget, QComboBox, QDoubleSpinBox)

import av
from transcode.pyqtgui.qfilterconfig import QFilterConfig
from . import ChannelMix
from functools import partial


class ChanMixDlg(QFilterConfig):
    def _createControls(self):
        self.setWindowTitle("Configure Channel Mixer")

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

        hlayout = QHBoxLayout()

        self.destLayout = QComboBox(self)
        self.destLayout.addItem("Mono", "mono")
        self.destLayout.addItem("2.0 Stereo", "stereo")
        self.destLayout.addItem("2.1 Stereo", "2.1")
        self.destLayout.addItem("3.0 Stereo", "3.0")
        self.destLayout.addItem("3.1 Stereo", "3.1")
        # self.destLayout.addItem("3.0 Surround", "259")
        # self.destLayout.addItem("4.0 Quad", "51")
        self.destLayout.addItem("4.0 Surround", "4.0")
        self.destLayout.addItem("4.1 Surround", "4.1")
        self.destLayout.addItem("5.0 Surround", "5.0")
        self.destLayout.addItem("5.0 Surround (Side)", "5.0(side)")
        self.destLayout.addItem("5.1 Surround", "5.1")
        self.destLayout.addItem("5.1 Surround (Side)", "5.1(side)")
        # self.destLayout.addItem("6.0 Hexagonal", "6.0")
        self.destLayout.addItem("6.0 Hexagonal (Side)", "6.0")
        # self.destLayout.addItem("6.1 Hexagonal", "6.0")
        self.destLayout.addItem("6.1 Hexagonal (Side)", "6.1")
        self.destLayout.addItem("7.0 Surround", "7.0")
        self.destLayout.addItem("7.1 Surround", "7.1")
        self.destLayout.addItem("7.1 Surround (Wide)", "7.1(wide)")

        layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Output Layout", self))
        hlayout.addWidget(self.destLayout)

        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)

        hlayout.addStretch()
        self._matrixlayout = QGridLayout()
        hlayout.addLayout(self._matrixlayout)
        hlayout.addStretch()

        self._matrixwidgets = []
        self.destLayout.currentIndexChanged.connect(self._handleLayoutChange)
        self._prepareDlgButtons()

    def createNewFilterInstance(self):
        return ChannelMix()

    def _createMatrixLayout(self, srclayout, destlayout, matrix):
        for widget in self._matrixwidgets:
            widget.deleteLater()

        self._matrixwidgets.clear()

        for j, channel in enumerate(destlayout.channels):
            label = QLabel(channel.name, self)
            self._matrixlayout.addWidget(label, j+1, 0)
            self._matrixwidgets.append(label)

        for k, channel in enumerate(srclayout.channels):
            label = QLabel(channel.name, self)
            self._matrixlayout.addWidget(label, 0, k+1)
            self._matrixwidgets.append(label)

        for j in range(len(destlayout.channels)):
            for k in range(len(srclayout.channels)):
                sb = QDoubleSpinBox(self)
                sb.setDecimals(2)
                sb.setMinimum(-8)
                sb.setMaximum(8)

                try:
                    sb.setValue(matrix[j, k])

                except IndexError:
                    pass

                sb.valueChanged.connect(
                    partial(self._handleMatrixValueChange, j, k))
                self._matrixlayout.addWidget(sb, j+1, k+1)
                self._matrixwidgets.append(sb)

    def _handleMatrixValueChange(self, j, k, value):
        try:
            self.filtercopy.matrix[j, k] = value

        except IndexError:
            return

        self.isModified()

    def _handleLayoutChange(self, value):
        if self.filtercopy.source is not None:
            try:
                srclayout = av.AudioLayout(self.filtercopy.source.layout)

            except Exception:
                return

            try:
                destlayout = av.AudioLayout(self.destLayout.currentData())

            except Exception:
                return

            self.filtercopy.layout = self.destLayout.currentData()
            self._createMatrixLayout(
                srclayout, destlayout, self.filtercopy.matrix)
            self.isModified()

    def _resetControls(self):
        if self.filtercopy.source is not None:
            try:
                srclayout = av.AudioLayout(self.filtercopy.source.layout)

            except Exception:
                return

            if self.filtercopy.layout:
                try:
                    destlayout = av.AudioLayout(self.filtercopy.layout)

                except Exception:
                    return

                self.destLayout.blockSignals(True)
                index = self.destLayout.findData(self.filtercopy.layout)
                self.destLayout.setCurrentIndex(index)
                self.destLayout.blockSignals(False)
                self._createMatrixLayout(
                    srclayout, destlayout, self.filtercopy.matrix)

            else:
                try:
                    destlayout = srclayout

                except Exception:
                    return

                self.destLayout.blockSignals(True)
                index = self.destLayout.findData(self.filtercopy.layout)
                self.destLayout.setCurrentIndex(index)
                self.destLayout.blockSignals(False)
                self._createMatrixLayout(
                    srclayout, destlayout, self.filtercopy.matrix)
