from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QPushButton, QMenu)
from PyQt5.QtCore import QSize, pyqtSignal

from matroska.chapters import ChapterAtom as InputChapterAtom
from matroska.chapters import ChapterDisplay as InputChapterDisplay
from .current import QChapterTree


class QChaptersWidget(QWidget):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)

        self.chapterTree = QChapterTree(self)
        self.chapterTree.contentsModified.connect(self.contentsModified)
        layout.addWidget(self.chapterTree)
        self.chapterTree.setMinimumWidth(640)
        self.chapterTree.setMinimumHeight(240)

        btnlayout = QHBoxLayout()
        layout.addLayout(btnlayout)

        self.importBtn = QPushButton(
            "&Import existing Edition Entries from input...", self)
        self.removeBtn = QPushButton("&Remove selected...", self)
        self.importBtn.clicked.connect(self.chapterTree.addFromInput)
        self.removeBtn.clicked.connect(self.chapterTree.askDeleteSelected)

        btnlayout.addWidget(self.importBtn)
        btnlayout.addWidget(self.removeBtn)
        btnlayout.addStretch()

    def setData(self, tracks, tags, chapters):
        for track in tracks:
            if track.type == "video":
                self.vtrack = track
                break

        else:
            self.vtrack = None

        self.chapterTree.setData(self.vtrack, tags, chapters)

    def handleSelectionChanged(self):
        self.removeBtn.setEnabled(
            len(self.chapterTree.selectionModel().selectedRows()) > 0)
