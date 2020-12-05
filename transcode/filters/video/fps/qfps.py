from PyQt5.QtCore import Qt, pyqtSlot, QRegExp, QTime
from PyQt5.QtGui import QRegExpValidator, QPen, QColor
from PyQt5.QtWidgets import (QAction, QLabel, QSpinBox, QGridLayout, QVBoxLayout,
                             QHBoxLayout, QLineEdit, QScrollArea, QWidget, QComboBox)

from functools import partial
from fractions import Fraction as QQ
from transcode.pyqtgui.qfilterconfig import QFilterConfig
from . import Fps
import regex


class FpsDlg(QFilterConfig):
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

        regex = QRegExp(r"^(\d+(?:\.\d+)?|\.\d+|\d+/\d+)$")
        validator = QRegExpValidator(regex)

        fpsLabel = QLabel("Frame rate:", self)
        self.fpsEdit = QLineEdit(self)
        self.fpsEdit.setText("24000/1001")
        self.fpsEdit.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.fpsEdit.setValidator(validator)
        self.fpsEdit.textChanged.connect(self.handleRateChanged)

        hlayout = QHBoxLayout()
        hlayout.addWidget(fpsLabel)
        hlayout.addWidget(self.fpsEdit)

        layout.addLayout(hlayout)

        self._prepareDlgButtons()

    def createNewFilterInstance(self):
        return Fps()

    @pyqtSlot(str)
    def handleRateChanged(self, value):
        if not regex.match(r"^(\d+(?:\.\d+)?|\.\d+|\d+/\d+)$", value):
            return

        if regex.match(r"^\d+/\d+$", value):
            value = QQ(value)

        elif regex.match(r"^\d+$", sar):
            value = int(value)

        else:
            value = float(value)

        self.filtercopy.rate = value
        self.isModified()

    def _resetControls(self):
        self.fpsEdit.blockSignals(True)
        self.fpsEdit.setText(f"{self.filtercopy.rate}")
        self.fpsEdit.blockSignals(False)
