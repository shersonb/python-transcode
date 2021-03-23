from PyQt5.QtWidgets import QWidget, QDialog, QTabWidget, QVBoxLayout, QHBoxLayout, QPushButton
from PyQt5.QtCore import pyqtSignal, pyqtSlot, Qt

from .qtags import QTagsWidget
from .qattachments import QAttachmentsWidget
from .qchapters import QChaptersWidget
from ..tags import Tags
from ..chapters import Editions
from ..attachments import Attachments

from copy import deepcopy


class QMatroskaConfig(QTabWidget):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.tagsTab = QTagsWidget(self)
        self.tagsTab.contentsModified.connect(self.contentsModified)
        self.addTab(self.tagsTab, "Tags")

        self.attachmentsTab = QAttachmentsWidget(self)
        self.attachmentsTab.contentsModified.connect(self.contentsModified)
        self.addTab(self.attachmentsTab, "Attachments")

        self.chaptersTab = QChaptersWidget(self)
        self.chaptersTab.contentsModified.connect(self.contentsModified)
        self.addTab(self.chaptersTab, "Chapters")

    def setData(self, tags, tracks, editions, attachments):
        self.tagsTab.setData(tags, tracks, editions, attachments)
        self.attachmentsTab.setData(tags, attachments)
        self.chaptersTab.setData(tracks, tags, editions)


class QMatroskaConfigDlg(QDialog):
    settingsApplied = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        layout = QVBoxLayout()
        self.setLayout(layout)

        self.tabs = QMatroskaConfig(self)
        self.tabs.contentsModified.connect(self.isModified)
        layout.addWidget(self.tabs)

        btnlayout = QHBoxLayout()
        layout.addLayout(btnlayout)

        btnlayout.addStretch()

        self.okayBtn = QPushButton("&OK", self)
        self.applyBtn = QPushButton("&Apply", self)
        self.resetBtn = QPushButton("&Reset", self)
        self.closeBtn = QPushButton("&Close", self)

        self.okayBtn.clicked.connect(self.applyAndClose)
        self.applyBtn.clicked.connect(self.apply)
        self.resetBtn.clicked.connect(self.reset)
        self.closeBtn.clicked.connect(self.close)

        btnlayout.addWidget(self.okayBtn)
        btnlayout.addWidget(self.applyBtn)
        btnlayout.addWidget(self.resetBtn)
        btnlayout.addWidget(self.closeBtn)

    def isModified(self):
        self.okayBtn.setEnabled(True)
        self.applyBtn.setEnabled(True)
        self.resetBtn.setEnabled(True)
        self.closeBtn.setText("&Cancel")

    def notModified(self):
        self.okayBtn.setEnabled(False)
        self.applyBtn.setEnabled(False)
        self.resetBtn.setEnabled(False)
        self.closeBtn.setText("&Close")

    def apply(self):
        self.output_file.tags = self.tags
        self.output_file.chapters = self.editions
        self.output_file.attachments = self.attachments
        self.settingsApplied.emit()
        self.notModified()

    def reset(self):
        if self.output_file is not None:
            tracks = self.output_file.tracks
            input_files = self.output_file.config.input_files

            memo = {id(track): track for track in tracks}

            self.tags, self.attachments, self.editions = deepcopy((
                    self.output_file.tags or Tags(),
                    self.output_file.attachments or Attachments(),
                    self.output_file.chapters or Editions(),
                ), memo)

            self.tags.parent = self.output_file
            self.attachments.parent = self.output_file
            self.editions.parent = self.output_file

            self.setWindowTitle(
                f"Matroska Options — {self.output_file.title} [{self.output_file.outputpathrel}]")

        else:
            input_files = tracks = self.tags = self.attachments = self.editions = None
            self.setWindowTitle("Matroska Options")

        self.tabs.setData(self.tags, tracks, self.editions, self.attachments)
        self.notModified()

    def applyAndClose(self):
        self.apply()
        self.close()

    def setOutputFile(self, output_file):
        self.output_file = output_file
        self.reset()
