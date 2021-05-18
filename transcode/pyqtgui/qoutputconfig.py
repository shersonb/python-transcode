from .qoutputtracklist import OutputTrackList
from transcode.containers.basewriter import BaseWriter

from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton,
                             QLabel, QLineEdit, QFileDialog, QDialog,
                             QCheckBox, QDoubleSpinBox)
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon

import os


class QCheckBoxMatchHeight(QCheckBox):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._hwidget = None

    def sizeHint(self):
        sh = super().sizeHint()

        if isinstance(self._hwidget, QWidget):
            other = self._hwidget.sizeHint()
            sh.setHeight(other.height())

        return sh

    def setHeightMatch(self, widget):
        self._hwidget = widget
        self.updateGeometry()


class QOutputConfig(QWidget):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.trackTable = OutputTrackList(self)
        self.trackTable.contentsModified.connect(self.isModified)
        layout.addWidget(self.trackTable)

        self.titleLabel = QLabel("Title:", self)
        self.titleEdit = QLineEdit(self)
        self.titleEdit.textChanged.connect(self.setOutputTitle)

        sublayout = QHBoxLayout()
        sublayout.addWidget(self.titleLabel)
        sublayout.addWidget(self.titleEdit)
        layout.addLayout(sublayout)

        self.fileLabel = QLabel("File name:", self)
        self.fileEdit = QLineEdit(self)
        self.fileEdit.textChanged.connect(self.setOutputPath)

        self.browseBtn = QPushButton(self)
        self.browseBtn.clicked.connect(self.execBrowseDlg)
        self.browseBtn.setIcon(QIcon.fromTheme("document-open"))

        sublayout = QHBoxLayout()
        sublayout.addWidget(self.fileLabel)
        sublayout.addWidget(self.fileEdit)
        sublayout.addWidget(self.browseBtn)
        layout.addLayout(sublayout)

        sublayout = QHBoxLayout()
        self.targetSizeCheckBox = QCheckBoxMatchHeight(
            "&Target File Size (Overrides settings in video encoder)", self)

        self.targetSizeSpinBox = QDoubleSpinBox(self)
        self.targetSizeSpinBox.setMinimum(1)
        self.targetSizeSpinBox.setDecimals(3)
        self.targetSizeSpinBox.setMaximum(65536)
        self.targetSizeSpinBox.setSuffix(" MB")

        self.targetSizeCheckBox.setHeightMatch(self.targetSizeSpinBox)

        self.targetSizeCheckBox.stateChanged.connect(self.setTargetSizeMode)
        self.targetSizeSpinBox.valueChanged.connect(self.setTargetSize)

        sublayout.addWidget(self.targetSizeCheckBox)
        sublayout.addWidget(self.targetSizeSpinBox)
        sublayout.addStretch()
        layout.addLayout(sublayout)

        self.settingsBtn = QPushButton("Con&figure Container...", self)
        self.settingsBtn.setIcon(QIcon.fromTheme("preferences-other"))
        self.settingsBtn.clicked.connect(self.configureContainer)

        self.btnlayout = QHBoxLayout()
        self.btnlayout.addStretch()
        self.btnlayout.addWidget(self.settingsBtn)
        layout.addLayout(self.btnlayout)

        self.setOutputFile(None)

    def setOutputTitle(self, title):
        self.output_file.title = title
        self.isModified()

    def setOutputPath(self, path):
        self.output_file.outputpathrel = path
        self.isModified()

    def setTargetSize(self, value):
        if self.targetSizeCheckBox.checkState():
            self.output_file.targetsize = value*1024**2
            self.isModified()

    def setTargetSizeMode(self, flag):
        self.targetSizeSpinBox.setVisible(flag)

        if flag:
            self.output_file.targetsize = (self.targetSizeSpinBox.value()
                                           * 1024**2)

        else:
            self.output_file.targetsize = None

        self.isModified()

    def execBrowseDlg(self):
        exts = ' '.join(f'*{ext}' for ext in self.output_file.extensions)
        filters = (f"{self.output_file.fmtname} Files ({exts})")

        if self.output_file.config and self.output_file.config.workingdir:
            fileName = os.path.join(
                self.output_file.config.workingdir, self.fileEdit.text())

        else:
            fileName = self.fileEdit.text()

        fileName, _ = QFileDialog.getSaveFileName(self, "Save File",
                                                  fileName, filters)

        if fileName:
            if (self.output_file.config
                    and self.output_file.config.workingdir):
                fileName = os.path.join(
                    self.output_file.config.workingdir, fileName)

                if not os.path.relpath(
                        fileName,
                        self.output_file.config.workingdir).startswith("../"):
                    fileName = os.path.relpath(
                        fileName, self.output_file.config.workingdir)

            self.fileEdit.setText(fileName)
            self.isModified()
            return True

        return False

    def isModified(self):
        self._modified = True
        self.contentsModified.emit()

    def _resetMinimumSize(self):
        self.targetSizeSpinBox.setMinimum(
            self.output_file.minimumSize()/1024**2)

    def notModified(self):
        self._modified = False

    def modified(self):
        return self._modified

    def updateOutputPath(self):
        self.fileEdit.blockSignals(True)

        if (isinstance(self.output_file, BaseWriter)
                and self.output_file.outputpathrel):
            self.fileEdit.setText(self.output_file.outputpathrel or "")

        else:
            self.fileEdit.setText("")

        self.fileEdit.blockSignals(False)

    def setOutputFile(self, output_file=None):
        self.notModified()
        self.output_file = output_file

        if output_file is not None:
            self.trackTable.setOutputFile(output_file)
            self.trackTable.contentsModified.connect(self._resetMinimumSize)

            self.titleEdit.blockSignals(True)
            self.titleEdit.setText(output_file.title or "")
            self.titleEdit.blockSignals(False)

            self.updateOutputPath()

            self.targetSizeCheckBox.blockSignals(True)
            self.targetSizeCheckBox.setTristate(False)
            self.targetSizeCheckBox.setCheckState(
                2 if output_file.targetsize is not None else 0)
            self.targetSizeCheckBox.blockSignals(False)

            self.targetSizeSpinBox.setHidden(output_file.targetsize is None)

            if output_file.targetsize:
                output_file.loadOverhead()
                self.targetSizeSpinBox.blockSignals(True)
                self._resetMinimumSize()
                self.targetSizeSpinBox.setValue(output_file.targetsize/1024**2)
                self.targetSizeSpinBox.blockSignals(False)

            self.settingsBtn.setEnabled(output_file.QtDlgClass() is not None)
            self.settingsBtn.setText(f"{output_file.fmtname} Options...")

        else:
            self.titleEdit.blockSignals(True)
            self.titleEdit.setText("")
            self.titleEdit.blockSignals(False)

            self.fileEdit.blockSignals(True)
            self.fileEdit.setText("")
            self.fileEdit.blockSignals(False)

            self.trackTable.setOutputFile(None)

            self.settingsBtn.setEnabled(False)
            self.settingsBtn.setText("Options...")

            self.targetSizeCheckBox.blockSignals(True)
            self.targetSizeCheckBox.setTristate(True)
            self.targetSizeCheckBox.setCheckState(1)
            self.targetSizeCheckBox.blockSignals(False)
            self.targetSizeSpinBox.setHidden(True)

        self.setEnabled(output_file is not None)

    def configureContainer(self):
        dlg = self.output_file.QtDlg(self)

        if dlg is not None:
            dlg.settingsApplied.connect(self.contentsModified)
            dlg.exec_()
            self._resetMinimumSize()


class QOutputConfigDlg(QDialog):
    def __init__(self, input_files, filters, output_file=None,
                 *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.output_file = output_file
        self.widget = QOutputConfig(input_files, filters, output_file, self)
        self.widget.applyBtn.setHidden(True)
        self.updateTitle()
        self.widget.okayBtn.clicked.connect(self.applyAndClose)
        self.widget.closeBtn.clicked.connect(self.close)
        self.widget.applyBtn.clicked.connect(self.apply)
        self.modified.connect(self.updateTitle)
        layout.addWidget(self.widget)

    def applyAndClose(self):
        self.apply()
        self.close()

    def apply(self):
        self.output_file = self.widget._output_file_copy
        self.done(1)
        self.widget.notModified()

    @property
    def modified(self):
        return self.widget.modified

    def updateTitle(self):
        self.setWindowTitle(
            f"Configure — {self.widget._output_file_copy.title}"
            f" [{self.widget._output_file_copy.outputpathrel}]")
