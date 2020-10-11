from .qoutputtracklist import OutputListView
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel, QLineEdit, QFileDialog, QDialog, QCheckBox, QDoubleSpinBox
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5.QtGui import QIcon
import os

class QOutputConfig(QWidget):
    modified = pyqtSignal()

    def __init__(self, input_files, filters, output_file=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.trackTable = OutputListView(input_files, filters, None, self)
        self.trackTable.contentsChanged.connect(self.isModified)
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
        self.targetSizeCheckBox = QCheckBox("&Target File Size (Overrides settings in video encoder)", self)
        self.targetSizeSpinBox = QDoubleSpinBox(self)
        self.targetSizeSpinBox.setMinimum(1)
        self.targetSizeSpinBox.setDecimals(3)
        self.targetSizeSpinBox.setMaximum(65536)
        self.targetSizeSpinBox.setSuffix(" MB")

        self.targetSizeCheckBox.stateChanged.connect(self.setTargetSizeMode)
        self.targetSizeSpinBox.valueChanged.connect(self.setTargetSize)

        sublayout.addWidget(self.targetSizeCheckBox)
        sublayout.addWidget(self.targetSizeSpinBox)
        sublayout.addStretch()
        layout.addLayout(sublayout)


        self.settingsBtn = QPushButton("Con&figure Container...", self)
        self.settingsBtn.setIcon(QIcon.fromTheme("preferences-other"))

        self.okayBtn = QPushButton("&OK", self)
        self.applyBtn = QPushButton("&Apply", self)
        self.resetBtn = QPushButton("&Reset", self)
        self.resetBtn.clicked.connect(self.reset)
        self.closeBtn = QPushButton("&Close", self)

        self.btnlayout = QHBoxLayout()
        self.btnlayout.addWidget(self.settingsBtn)
        self.btnlayout.addStretch()
        self.btnlayout.addWidget(self.okayBtn)
        self.btnlayout.addWidget(self.applyBtn)
        self.btnlayout.addWidget(self.resetBtn)
        self.btnlayout.addWidget(self.closeBtn)
        layout.addLayout(self.btnlayout)

        self.setOutputFile(output_file)

    def setOutputTitle(self, title):
        self._output_file_copy.title = title
        self.isModified()

    def setOutputPath(self, path):
        self._output_file_copy.outputpathrel = path
        self.isModified()

    def setTargetSize(self, value):
        self._output_file_copy.targetsize = value*1024**2
        self.isModified()

    def setTargetSizeMode(self, flag):
        self.targetSizeSpinBox.setVisible(flag)

        if flag:
            self._output_file_copy.targetsize = self.targetSizeSpinBox.value()*1024**2

        else:
            self._output_file_copy.targetsize = None

        self.isModified()

    def execBrowseDlg(self):
        filters = f"{self._output_file_copy.fmtname} Files ({' '.join(f'*{ext}' for ext in self._output_file_copy.extensions)})"

        if self._output_file_copy.config and self._output_file_copy.config.workingdir:
            fileName = os.path.join(self._output_file_copy.config.workingdir, self.fileEdit.text())

        else:
            fileName = self.fileEdit.text()

        fileName, _ = QFileDialog.getSaveFileName(self, "Save File",
                fileName, filters)

        if fileName:
            if self._output_file_copy.config and self._output_file_copy.config.workingdir:
                fileName = os.path.join(self._output_file_copy.config.workingdir, fileName)

                if not os.path.relpath(fileName, self._output_file_copy.config.workingdir).startswith("../"):
                    fileName = os.path.relpath(fileName, self._output_file_copy.config.workingdir)

            self.fileEdit.setText(fileName)

            self.isModified()
            return True
        return False

    def isModified(self):
        self._modified = True
        self.okayBtn.setEnabled(True)
        self.applyBtn.setEnabled(True)
        self.resetBtn.setEnabled(True)
        self.closeBtn.setText("&Cancel")
        self.modified.emit()

    def notModified(self):
        self._modified = True
        self.okayBtn.setEnabled(False)
        self.applyBtn.setEnabled(False)
        self.resetBtn.setEnabled(False)
        self.closeBtn.setText("&Close")

    def setOutputFile(self, output_file=None):
        self.notModified()
        self._output_file = output_file

        if output_file is not None:
            self._output_file_copy = output_file.copy()
            self._output_file_copy.config = output_file.config
            self.trackTable.setOutputFile(self._output_file_copy)

            self.titleEdit.blockSignals(True)
            self.titleEdit.setText(self._output_file_copy.title or "")
            self.titleEdit.blockSignals(False)

            self.fileEdit.blockSignals(True)
            self.fileEdit.setText(self._output_file_copy.outputpathrel or "")
            self.fileEdit.blockSignals(False)

            self.targetSizeCheckBox.blockSignals(True)
            self.targetSizeCheckBox.setCheckState(2 if self._output_file_copy.targetsize is not None else 0)
            self.targetSizeCheckBox.blockSignals(False)

            self.targetSizeSpinBox.setHidden(self._output_file_copy.targetsize is None)

            if self._output_file_copy.targetsize:
                self.targetSizeSpinBox.blockSignals(True)
                self.targetSizeSpinBox.setValue(self._output_file_copy.targetsize/1024**2)
                self.targetSizeSpinBox.blockSignals(False)

            self.browseBtn.setEnabled(True)

            self.settingsBtn.setEnabled(hasattr(self._output_file_copy, "QtDlgClass") and self._output_file_copy.QtDlgClass is not None)

        else:
            self._output_file_copy = None
            self.trackTable.setOutputFile(None)
            self.settingsBtn.setEnabled(False)
            self.browseBtn.setEnabled(False)

            self.targetSizeCheckBox.blockSignals(True)
            self.targetSizeCheckBox.setCheckState(1)
            self.targetSizeCheckBox.blockSignals(False)
            self.targetSizeSpinBox.setHidden(True)

    def reset(self):
        self.setOutputFile(self._output_file)

class QOutputConfigDlg(QDialog):
    def __init__(self, input_files, filters, output_file=None, *args, **kwargs):
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
        self.setWindowTitle(f"Configure — {self.widget._output_file_copy.title} [{self.widget._output_file_copy.outputpathrel}]")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Output File Configuration.")
    parser.add_argument("file", action='store', help="Config file")
    parser.add_argument("-n", action='store', help="Select output file to configure.", default=0, type=int)
    args = parser.parse_args()

    from transcode.config.ebml import ConfigElement
    config = ConfigElement.load(args.file)
    outfile = config.output_files[args.n]

    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    cfg = QOutputConfigDlg(config.input_files, config.filter_chains, outfile)

    if cfg.exec_():
        config.output_files[args.n] = cfg.output_file

        import time
        T = time.localtime()
        os.rename(args.file, f"{args.file}-backup-{T.tm_year:04d}.{T.tm_mon:02d}.{T.tm_mday:02d}-{T.tm_hour:02d}.{T.tm_min:02d}.{T.tm_sec:02d}")
        ConfigElement.save(config, args.file)
