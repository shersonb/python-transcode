from PyQt5.QtCore import Qt, pyqtSignal, pyqtBoundSignal
from PyQt5.QtGui import QFont, QIcon
from .qinputtracklist import QInputTrackList
# TODO: Filters
from .qoutputfiles import QOutputFileList
from .qoutputconfig import QOutputConfig

from PyQt5.QtWidgets import (QApplication, QWidget, QMainWindow,
                             QVBoxLayout, QHBoxLayout, QSplitter, QMessageBox,
                             QLabel, QAction, QFileDialog, QToolBar)

import threading
from transcode.config import Config
from transcode.config.ebml import ConfigElement
import os
import sys
import types
import traceback
import time


class QConfig(QWidget):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        layout = QVBoxLayout()

        self.setLayout(layout)
        splitter = QSplitter(Qt.Vertical, self)
        layout.addWidget(splitter)

        inputWidget = QWidget(splitter)

        inputLayout = QVBoxLayout()
        inputLayout.setContentsMargins(0, 8, 0, 0)
        inputWidget.setLayout(inputLayout)

        inputLabelLayout = QHBoxLayout()

        inputTrackListLabel = QLabel("Input Files", inputWidget)
        inputTrackListLabel.setFont(
            QFont("DejaVu Serif", 18, QFont.Bold, italic=True))
        inputLabelLayout.addWidget(inputTrackListLabel)

        inputLabelLayout.addStretch()
        inputLayout.addLayout(inputLabelLayout)

        self.inputTrackList = QInputTrackList(inputWidget)
        self.inputTrackList.contentsModified.connect(self.contentsModified)

        inputLayout.addWidget(self.inputTrackList)

        splitter.addWidget(inputWidget)

        subsplitter = QSplitter(Qt.Horizontal, splitter)

        outputFilesWidget = QWidget(subsplitter)

        outputFilesLayout = QVBoxLayout()
        outputFilesLayout.setContentsMargins(0, 16, 0, 0)
        outputFilesWidget.setLayout(outputFilesLayout)

        outputFilesLabelLayout = QHBoxLayout()

        outputFilesLabel = QLabel("Output Files", outputFilesWidget)
        outputFilesLabel.setFont(
            QFont("DejaVu Serif", 18, QFont.Bold, italic=True))
        outputFilesLabelLayout.addWidget(outputFilesLabel)

        outputFilesLabelLayout.addStretch()
        outputFilesLayout.addLayout(outputFilesLabelLayout)

        self.outputFiles = QOutputFileList(outputFilesWidget)
        self.outputFiles.contentsModified.connect(self.contentsModified)

        outputFilesLayout.addWidget(self.outputFiles)

        outputConfigWidget = QWidget(subsplitter)

        outputConfigLayout = QVBoxLayout()
        outputConfigLayout.setContentsMargins(0, 16, 0, 0)
        outputConfigWidget.setLayout(outputConfigLayout)

        outputConfigLabelLayout = QHBoxLayout()

        outputConfigLabel = QLabel("Tracks", outputConfigWidget)
        outputConfigLabel.setFont(
            QFont("DejaVu Serif", 18, QFont.Bold, italic=True))
        outputConfigLabelLayout.addWidget(outputConfigLabel)

        outputConfigLabelLayout.addStretch()
        outputConfigLayout.addLayout(outputConfigLabelLayout)

        self.outputConfig = QOutputConfig(self)
        self.outputConfig.contentsModified.connect(self.contentsModified)

        outputConfigLayout.addWidget(self.outputConfig)

        splitter.addWidget(subsplitter)

        subsplitter.addWidget(outputFilesWidget)
        subsplitter.addWidget(outputConfigWidget)
        self.setConfig(None)

    def selectOutputFile(self, newindex, oldindex):
        output_file = newindex.data(Qt.UserRole)
        self.outputConfig.setOutputFile(output_file)

    def setConfig(self, config):
        self.config = config

        if config is not None:
            self.inputTrackList.setInputFiles(config.input_files)

            # TODO: Filters

            self.outputFiles.setOutputFiles(config.output_files)
            self.outputConfig.setOutputFile(None)
            self.outputFiles.selectionModel().currentRowChanged.connect(self.selectOutputFile)

            if self.outputFiles.model().rowCount():
                self.outputFiles.setCurrentIndex(
                    self.outputFiles.model().index(0, 0))

        # else:
            # self.inputTrackList.setInputFiles(None)
            # self.outputFiles.setOutputFiles(None)
            # self.inputTrackList.setInputFiles(None)


class QConfigWindow(QMainWindow):
    fileLoading = pyqtSignal()
    fileLoaded = pyqtSignal()
    configLoaded = pyqtSignal(Config)
    delayedOpen = pyqtSignal()
    delayedNew = pyqtSignal()
    delayedExit = pyqtSignal()
    exceptionCaptured = pyqtSignal(type, BaseException, types.TracebackType)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("QTranscode Editor")
        self.configWidget = QConfig(self)
        self.setCentralWidget(self.configWidget)
        self.configWidget.contentsModified.connect(self.isModified)

        self.newAct = QAction("&New", self, shortcut="Ctrl+N",
                              triggered=self.fileNew)
        self.newAct.setIcon(QIcon.fromTheme("document-new"))
        self.addAction(self.newAct)

        self.openAct = QAction("&Open...", self, shortcut="Ctrl+O",
                               triggered=self.fileOpen)
        self.openAct.setIcon(QIcon.fromTheme("document-open"))
        self.addAction(self.openAct)

        self.saveAct = QAction("&Save", self, shortcut="Ctrl+S",
                               triggered=self.fileSave, enabled=False)
        self.saveAct.setIcon(QIcon.fromTheme("document-save"))
        self.addAction(self.saveAct)

        self.saveAsAct = QAction("Save As...", self, shortcut="Ctrl+Shift+S",
                                 triggered=self.fileSaveAs, enabled=False)
        self.saveAsAct.setIcon(QIcon.fromTheme("document-save-as"))
        self.addAction(self.saveAsAct)

        self.exitAct = QAction("E&xit", self, shortcut="Ctrl+Q",
                               triggered=self.close)
        self.exitAct.setIcon(QIcon.fromTheme("application-exit"))
        self.addAction(self.exitAct)

        self.toolBar = QToolBar(self)
        self.toolBar.addAction(self.newAct)
        self.toolBar.addAction(self.openAct)
        self.toolBar.addAction(self.saveAct)
        self.toolBar.addAction(self.saveAsAct)
        self.toolBar.addSeparator()
        self.toolBar.addAction(self.exitAct)
        self.addToolBar(self.toolBar)

        self.configLoaded.connect(self.loadConfig)
        self.delayedOpen.connect(self.fileOpen)
        self.delayedNew.connect(self.fileNew)
        self.delayedExit.connect(self.close)

        self.fileLoading.connect(self.handleFileLoading)
        self.fileLoaded.connect(self.handleFileLoaded)
        self.exceptionCaptured.connect(self.handleException)

        self.loading = False
        self.loadConfig(Config())

    def isModified(self):
        self.saveAct.setEnabled(True)
        self._modified = True

    def notModified(self):
        self.saveAct.setEnabled(False)
        self._modified = False

    def loadConfig(self, config):
        self.config = config
        self.configWidget.setConfig(config)

        if config.configname:
            self.setWindowTitle(f"QTranscode Editor - [{config.configname}]")

        else:
            self.setWindowTitle("QTranscode Editor - Untitled")

        self.notModified()

    def fileNew(self):
        if self._modified:
            reply = self.saveChangesDlg()

            if reply == QMessageBox.Yes:
                self.fileSave(self.delayedNew)
                return

            elif reply == QMessageBox.Cancel:
                return

        self.loadConfig(Config())

    def fileOpen(self):
        if self._modified:
            reply = self.saveChangesDlg()

            if reply == QMessageBox.Yes:
                self.fileSave(self.delayedOpen)
                return

            elif reply == QMessageBox.Cancel:
                return

        filters = "All supported files (*.ptc *.ptc.gz *.ptc.bz2 *.ptc.xz)"
        fileName, _ = QFileDialog.getOpenFileName(self, "Open File",
                                                  None, filters)

        if fileName:
            t = threading.Thread(target=self.loadFile,
                                 args=(fileName,), kwargs={})
            t.start()

    def fileSave(self, signal=None, signalargs=()):
        if self.config.configname or self.saveDlg():
            t = threading.Thread(target=self._save, args=(signal, signalargs))
            t.start()
            return

        return False

    def saveDlg(self):
        filters = "Session files (*.ptc.xz)"

        defaultname = self.config.configname or "untitled.ptc.xz"
        fileName, _ = QFileDialog.getSaveFileName(self, "Save File",
                                                  str(defaultname), filters)

        return fileName

    def _save(self, signal=None, signalargs=()):
        self.fileLoading.emit()
        fileName = self.config.configname

        try:
            if os.path.isfile(fileName):
                T = time.localtime()
                backup = f"{fileName}-backup-{T.tm_year:04d}.{T.tm_mon:02d}.{T.tm_mday:02d}-{T.tm_hour:02d}.{T.tm_min:02d}.{T.tm_sec:02d}"

                try:
                    os.rename(fileName, backup)

                except:
                    backup = None

            else:
                backup = None

            try:
                ConfigElement.save(self.config, fileName)

            except BaseException as exc:
                self.exceptionCaptured.emit(*sys.exc_info())

                if backup:
                    os.rename(backup, fileName)

            self._modified = False

        finally:
            self.fileLoaded.emit()

        if isinstance(signal, (pyqtSignal, pyqtBoundSignal)):
            signal.emit(*signalargs)

    def fileSaveAs(self):
        fileName = self.saveDlg()

        if fileName:
            self.config.configname = fileName
            self.fileSave()
            self.setWindowTitle(
                f"QTranscode Editor - [{self.config.configname}]")

        return fileName

    def handleFileLoading(self):
        self.loading = True
        self.setDisabled(True)

    def handleFileLoaded(self):
        self.loading = False
        self.setDisabled(False)
        self.saveAct.setEnabled(False)
        self.saveAsAct.setEnabled(True)

    def loadFile(self, fileName):
        fileDir, _ = os.path.split(fileName)
        fileStem, _ = os.path.splitext(fileName)
        fileDir = os.path.abspath(fileDir)

        self.fileLoading.emit()

        try:
            config = ConfigElement.load(fileName)
            self.configLoaded.emit(config)

        except BaseException as exc:
            self.exceptionCaptured.emit(*sys.exc_info())

        finally:
            self.fileLoaded.emit()

    def saveChangesDlg(self):
        answer = QMessageBox.question(self, "Save Changes?", "Do you wish to save changes?",
                                      QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
        return answer

    def handleException(self, cls, exc, tb):
        print(traceback.format_exception(cls, exc, tb), file=sys.stderr)
        excmsg = QMessageBox(self)
        excmsg.setWindowTitle("Error")
        excmsg.setText("An exception was encountered\n\n%s" %
                       "".join(traceback.format_exception(cls, exc, tb)))
        excmsg.setStandardButtons(QMessageBox.Ok)
        excmsg.setIcon(QMessageBox.Critical)
        excmsg.exec_()

    def closeEvent(self, event):
        if self.loading:
            event.ignore()
            return

        if self._modified:
            reply = self.saveChangesDlg()

            if reply == QMessageBox.Yes:
                self.fileSave(self.delayedExit)
                event.ignore()
                return

            elif reply == QMessageBox.No:
                event.accept()

            elif reply == QMessageBox.Cancel:
                event.ignore()
                return

        event.accept()


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser(description="QTranscode Configuration.")
    parser.add_argument("file", action='store', help="Config file", nargs="?")
    args = parser.parse_args()

    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    win = QConfigWindow()
    win.show()

    if args.file:
        t = threading.Thread(target=win.loadFile, args=(args.file,), kwargs={})
        t.start()

    app.exec_()
    return win.config


if __name__ == "__main__":
    main()
