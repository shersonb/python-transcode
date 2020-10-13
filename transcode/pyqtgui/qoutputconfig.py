from .qoutputtracklist import OutputTrackList
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QLabel,
                             QLineEdit, QFileDialog, QDialog, QCheckBox, QDoubleSpinBox)
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt
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
    modified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self.trackTable = OutputTrackList(self)
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
        self.targetSizeCheckBox = QCheckBoxMatchHeight("&Target File Size (Overrides settings in video encoder)", self)

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

        #self.okayBtn = QPushButton("&OK", self)
        #self.applyBtn = QPushButton("&Apply", self)
        #self.resetBtn = QPushButton("&Reset", self)
        #self.resetBtn.clicked.connect(self.reset)
        #self.closeBtn = QPushButton("&Close", self)

        self.btnlayout = QHBoxLayout()
        self.btnlayout.addWidget(self.settingsBtn)
        self.btnlayout.addStretch()
        #self.btnlayout.addWidget(self.okayBtn)
        #self.btnlayout.addWidget(self.applyBtn)
        #self.btnlayout.addWidget(self.resetBtn)
        #self.btnlayout.addWidget(self.closeBtn)
        layout.addLayout(self.btnlayout)

        #if output_file is not None:
        self.setOutputFile(None)

    def setOutputTitle(self, title):
        output_file.title = title
        self.isModified()

    def setOutputPath(self, path):
        output_file.outputpathrel = path
        self.isModified()

    def setTargetSize(self, value):
        output_file.targetsize = value*1024**2
        self.isModified()

    def setTargetSizeMode(self, flag):
        self.targetSizeSpinBox.setVisible(flag)

        if flag:
            output_file.targetsize = self.targetSizeSpinBox.value()*1024**2

        else:
            output_file.targetsize = None

        self.isModified()

    def execBrowseDlg(self):
        filters = f"{output_file.fmtname} Files ({' '.join(f'*{ext}' for ext in output_file.extensions)})"

        if output_file.config and output_file.config.workingdir:
            fileName = os.path.join(output_file.config.workingdir, self.fileEdit.text())

        else:
            fileName = self.fileEdit.text()

        fileName, _ = QFileDialog.getSaveFileName(self, "Save File",
                fileName, filters)

        if fileName:
            if output_file.config and output_file.config.workingdir:
                fileName = os.path.join(output_file.config.workingdir, fileName)

                if not os.path.relpath(fileName, output_file.config.workingdir).startswith("../"):
                    fileName = os.path.relpath(fileName, output_file.config.workingdir)

            self.fileEdit.setText(fileName)

            self.isModified()
            return True
        return False

    def isModified(self):
        self._modified = True
        #self.okayBtn.setEnabled(True)
        #self.applyBtn.setEnabled(True)
        #self.resetBtn.setEnabled(True)
        #self.closeBtn.setText("&Cancel")
        self.modified.emit()

    def notModified(self):
        self._modified = True
        #self.okayBtn.setEnabled(False)
        #self.applyBtn.setEnabled(False)
        #self.resetBtn.setEnabled(False)
        #self.closeBtn.setText("&Close")

    def setOutputFile(self, output_file=None):
        self.notModified()
        self.output_file = output_file

        if output_file is not None:
            self.trackTable.setOutputFile(output_file)

            self.titleEdit.blockSignals(True)
            self.titleEdit.setText(output_file.title or "")
            self.titleEdit.blockSignals(False)

            self.fileEdit.blockSignals(True)
            self.fileEdit.setText(output_file.outputpathrel or "")
            self.fileEdit.blockSignals(False)

            self.targetSizeCheckBox.blockSignals(True)
            self.targetSizeCheckBox.setCheckState(2 if output_file.targetsize is not None else 0)
            self.targetSizeCheckBox.blockSignals(False)

            self.targetSizeSpinBox.setHidden(output_file.targetsize is None)

            if output_file.targetsize:
                self.targetSizeSpinBox.blockSignals(True)
                self.targetSizeSpinBox.setValue(output_file.targetsize/1024**2)
                self.targetSizeSpinBox.blockSignals(False)

            self.browseBtn.setEnabled(True)

            self.settingsBtn.setEnabled(hasattr(output_file, "QtDlgClass") and output_file.QtDlgClass is not None)

        else:
            self.trackTable.setOutputFile(None)
            self.settingsBtn.setEnabled(False)
            self.browseBtn.setEnabled(False)

            self.targetSizeCheckBox.blockSignals(True)
            self.targetSizeCheckBox.setCheckState(1)
            self.targetSizeCheckBox.blockSignals(False)
            self.targetSizeSpinBox.setHidden(True)

    #def reset(self):
        #self.setOutputFile(self._output_file)

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
