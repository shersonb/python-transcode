from PyQt5.QtCore import Qt
from .qinputtracklist import QInputTrackList
# TODO: Filters
from .qoutputfiles import QOutputFileList
from .qoutputconfig import QOutputConfig

from PyQt5.QtWidgets import QWidget, QDialog, QMainWindow, QVBoxLayout, QHBoxLayout, QSplitter

class QConfig(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        layout = QVBoxLayout()
        self.setLayout(layout)
        splitter = QSplitter(Qt.Vertical, self)
        layout.addWidget(splitter)

        self.inputTrackList = QInputTrackList(self)
        self.outputFiles = QOutputFileList(self)
        self.outputConfig = QOutputConfig(self)

        #layout.addWidget(self.inputTrackList)
        splitter.addWidget(self.inputTrackList)

        ##sublayout = QHBoxLayout()
        ##layout.addLayout(sublayout)
        sublayout = QSplitter(Qt.Horizontal, self)
        splitter.addWidget(sublayout)

        sublayout.addWidget(self.outputFiles)
        sublayout.addWidget(self.outputConfig)
        self.setConfig(None)

    def selectOutputFile(self, newindex, oldindex):
        self.outputConfig.setOutputFile(newindex.data(Qt.UserRole))

    def setConfig(self, config):
        self.config = config

        if config is not None:
            self.inputTrackList.setInputFiles(config.input_files)

            # TODO: Filters

            self.outputFiles.setOutputFiles(config.output_files)

            if self.outputFiles.model().rowCount():
                self.outputFiles.selectionModel().currentChanged.connect(self.selectOutputFile)
                self.outputFiles.setCurrentIndex(self.outputFiles.model().index(0, 0))
