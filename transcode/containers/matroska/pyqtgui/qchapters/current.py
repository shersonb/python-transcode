from PyQt5.QtWidgets import (QMenu, QHBoxLayout, QVBoxLayout, QLabel, QSpinBox,
                             QDialog, QPushButton, QCheckBox, QFileDialog)
from PyQt5.QtCore import Qt, QModelIndex, pyqtSignal

import os
import sys

import random
import xml.dom.minidom

from transcode.config.obj import Config
from transcode.containers.basewriter import BaseWriter
from transcode.containers.matroska.chapters import (
    ChapterAtom, ChapterDisplay, EditionEntry, Editions)
from transcode.pyqtgui.qitemmodel import Node, QItemModel
from transcode.pyqtgui.treeview import TreeView as QTreeView

from .available import AvailableEditionsSelection
from .currentnodes import EditionsNode
from .currentcols import (NameCol, DefaultCol, EnabledCol, OrderedCol,
                          HiddenCol, LangCol, CountryCol, StartCol, EndCol,
                          UIDCol)


class NewEditionDlg(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setWindowTitle("New Edition Entry")

        layout = QVBoxLayout()
        self.setLayout(layout)

        label = QLabel("Chapters:", self)
        self.chapterSpinBox = QSpinBox(self)
        self.chapterSpinBox.setMaximum(999)
        self.chapterSpinBox.setSpecialValueText("None")
        self.chapterSpinBox.valueChanged.connect(self._handleValueChanged)

        hlayout = QHBoxLayout()
        hlayout.addWidget(label)
        hlayout.addWidget(self.chapterSpinBox)
        layout.addLayout(hlayout)

        self.withDisplays = QCheckBox("Create ChapterDisplay entries", self)
        layout.addWidget(self.withDisplays)

        self.okayBtn = QPushButton("&OK", self)
        self.okayBtn.clicked.connect(self.accept)
        self.closeBtn = QPushButton("&Cancel", self)
        self.closeBtn.clicked.connect(self.reject)

        hlayout = QHBoxLayout()
        hlayout.addStretch()
        hlayout.addWidget(self.okayBtn)
        hlayout.addWidget(self.closeBtn)
        layout.addLayout(hlayout)

    def _handleValueChanged(self, value):
        self.withDisplays.setEnabled(bool(value))


class QChapterTree(QTreeView):
    contentsModified = pyqtSignal()
    _deletetitle = "Delete edition(s)/chapter(s)"
    _deletemsg = "Do you wish to delete the selected edition(s)/chapter(s)?"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumWidth(540)
        self.setDragDropMode(QTreeView.InternalMove)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setData(None, None, None)

    def contextMenuEvent(self, event):
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.mapToGlobal(event.pos()))

    def setData(self, track, tags, editions):
        self.tags = tags
        self.vtrack = track
        self.editions = editions

        if editions is not None:
            cols = [
                NameCol(tags, editions),
                DefaultCol(tags, editions),
                OrderedCol(tags, editions),
                EnabledCol(tags, editions),
                HiddenCol(tags, editions),
                LangCol(tags, editions),
                CountryCol(tags, editions),
                StartCol(tags, editions),
                EndCol(tags, editions),
                UIDCol(tags, editions),
            ]

            root = EditionsNode(editions)
            model = QItemModel(root, cols)
            self.setModel(model)
            self.expandAll()

        else:
            self.setModel(QItemModel(Node(None), []))

    def addEdition(self, row=-1):
        dlg = NewEditionDlg(self)

        if dlg.exec_():
            if row == -1:
                row = self.model().rowCount()

            existingUIDs = set()
            existingChapterUIDs = set()

            for edition in self.editions:
                existingUIDs.add(edition.UID)

                for atom in edition:
                    existingChapterUIDs.add(atom.UID)

            UID = random.randint(1, 2**64 - 1)

            while UID in existingUIDs:
                UID = random.randint(1, 2**64 - 1)

            edition = EditionEntry(UID=UID)

            for k in range(1, dlg.chapterSpinBox.value() + 1):
                UID = random.randint(1, 2**64 - 1)

                while UID in existingChapterUIDs:
                    UID = random.randint(1, 2**64 - 1)

                atom = ChapterAtom(UID, 0)
                edition.append(atom)
                existingChapterUIDs.add(UID)

                if dlg.withDisplays.checkState():
                    atom.displays.append(ChapterDisplay(f"Chapter {k}"))

            self.model().insertRow(row, edition)
            self.setCurrentIndex(self.model().index(row, 0))

    def addChapter(self, row=-1, parent=QModelIndex()):
        if row == -1:
            row = self.model().rowCount(parent)

        if row == 0:
            startFrame = 0

        else:
            startFrame = parent.child(row - 1, 0).data(Qt.UserRole).startFrame

        existingUIDs = set()

        for edition in self.editions:
            for chapter in edition:
                existingUIDs.add(chapter.UID)

        UID = random.randint(1, 2**64 - 1)

        while UID in existingUIDs:
            UID = random.randint(1, 2**64 - 1)

        chapter = ChapterAtom(UID, startFrame)
        self.model().insertRow(row, chapter, parent)
        self.setCurrentIndex(parent.child(row, 0))

    def addDisplay(self, row=-1, parent=QModelIndex()):
        if row == -1:
            row = self.model().rowCount(parent)

        self.model().insertRow(row, ChapterDisplay(""), parent)
        self.setCurrentIndex(parent.child(row, 0))
        self.edit(parent.child(row, 0))

    # TODO: Move importing of chapters from MatroskaReader
    # objects to transcode.containers.matroska.chapters.

    def importChapterAtom(self, chapteratom, existingChapterUIDs,
                          ordered=False):
        chapterUID = chapteratom.chapterUID

        while chapterUID in existingChapterUIDs:
            chapterUID = random.randint(1, 2**64 - 1)

        if self.vtrack is not None:
            m, s = divmod(float(chapteratom.chapterTimeStart)/10**9, 60)
            h, m = divmod(int(m), 60)
            startFrame = self.vtrack.source.frameIndexFromPts(
                chapteratom.chapterTimeStart + 8*10**6, "-")

            if ordered:
                endFrame = self.vtrack.source.frameIndexFromPts(
                    chapteratom.chapterTimeEnd + 8*10**6, "-")

            else:
                endFrame = None

            timeStart = timeEnd = None

        else:
            startFrame = endFrame = None
            timeStart = chapteratom.chapterTimeStart

            if ordered:
                timeEnd = chapteratom.chapterTimeEnd

            else:
                timeEnd = None

        displays = []

        for display in chapteratom.chapterDisplays:
            displays.append(ChapterDisplay(
                display.chapString,
                list(display.chapLanguages or []),
                langIETF=list(display.chapLanguagesIETF or []),
                countries=list(display.chapCountries or []),
            ))

        hidden = bool(chapteratom.chapterFlagHidden)
        enabled = bool(chapteratom.chapterFlagEnabled)

        existingChapterUIDs.add(chapterUID)
        return ChapterAtom(chapterUID, startFrame, endFrame,
                           timeStart, timeEnd, displays, hidden, enabled)

    def importEdition(self, edition):
        existingEditionUIDs = {edition.UID for edition in self.editions}
        existingChapterUIDs = {chapter.UID
                               for edition in self.editions
                               for chapter in edition
                               }

        editionUID = edition.editionUID
        ordered = bool(edition.editionFlagOrdered)

        while editionUID in existingEditionUIDs:
            editionUID = random.randint(1, 2**64 - 1)

        chapters = []

        for chapteratom in edition.chapterAtoms:
            chapters.append(self.importChapterAtom(
                chapteratom, existingChapterUIDs, ordered))

        default = bool(edition.editionFlagDefault)
        hidden = bool(edition.editionFlagHidden)
        return EditionEntry(chapters, editionUID, hidden, default, ordered)

    def addFromInput(self):
        input_files = self.editions.parent.config.input_files
        dlg = AvailableEditionsSelection(self)
        dlg.setInputFiles(input_files)

        if dlg.exec_():
            model = self.model()
            neweditions = []

            for input_file, edition in dlg.selectedEditions:
                neweditions.append(self.importEdition(edition))

            model.insertRows(model.rowCount(), neweditions, QModelIndex())

    def importChapters(self):
        model = self.model()
        filters = "Matroska Chapters (*.xml)"

        if (isinstance(self.editions, Editions)
                and isinstance(self.editions.parent, BaseWriter)
                and isinstance(self.editions.parent.config, Config)):
            path = os.path.abspath(self.editions.parent.config.workingdir)

        else:
            path = None

        fileName, _ = QFileDialog.getOpenFileName(
            self, "Import Matroska Chapters...", path, filters)

        if fileName:
            try:
                f = open(fileName, "r")
                x = xml.dom.minidom.parse(f)
                tags = Editions.fromXml(x, self.editions.parent)

                for tag in tags:
                    model.insertRow(model.rowCount(), tag)

                f.close()

            except Exception:
                self._handleException(*sys.exc_info())

    def exportChapters(self):
        model = self.model()
        sm = self.selectionModel()
        selected = [index.data(Qt.UserRole) for index in sm.selectedRows()]

        if (isinstance(self.editions, Editions)
                and isinstance(self.editions.parent, BaseWriter)
                and isinstance(self.editions.parent.config, Config)):
            path = os.path.abspath(self.editions.parent.config.workingdir)

        else:
            path = None

        filters = "Matroska Chapters (*.xml)"
        fileName, _ = QFileDialog.getSaveFileName(
            self, "Export Matroska Chapters...", path, filters)

        if fileName:
            try:
                x = model.root.value.toXml(selected)
                f = open(fileName, "w")
                print(x.toprettyxml(indent="    "), file=f)
                f.close()

            except Exception:
                self._handleException(*sys.exc_info())
