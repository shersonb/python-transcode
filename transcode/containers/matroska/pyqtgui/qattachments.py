from .quidspinbox import UIDDelegate
import sys
from PyQt5.QtCore import (Qt, QAbstractListModel, QAbstractItemModel, QAbstractTableModel,
                          QModelIndex, QFileInfo, QVariant, QItemSelectionModel, QItemSelection,
                          pyqtSignal, pyqtSlot, QMimeData, QDir)
from PyQt5 import QtCore
from PyQt5.QtWidgets import (QDialog, QLabel, QListWidgetItem, QListView, QVBoxLayout,
                             QHBoxLayout, QAbstractItemView, QMessageBox, QPushButton, QTreeView,
                             QTableView, QHeaderView, QSpinBox, QFrame, QLineEdit, QComboBox,
                             QCheckBox, QSpinBox, QDoubleSpinBox, QItemDelegate, QWidget,
                             QFileIconProvider, QMenu, QAction, QScrollArea, QFileDialog)
from PyQt5.QtGui import QFont, QIcon, QDrag, QBrush, QPainter, QRegExpValidator

from ..tags import Tag, Tags
from transcode.pyqtgui.qitemmodel import QItemModel, Node, ChildNodes, NoChildren
from transcode.pyqtgui.qimageview import QImageView
from transcode.pyqtgui.qlangselect import LanguageDelegate, LANGUAGES
from titlecase import titlecase
from functools import partial

from ..attachments import Attachments, AttachedFile, AttachmentRef
from matroska.attachments import AttachedFile as InputAttachedFile
from ..reader import MatroskaReader
from ...basereader import BaseReader
from ...basewriter import BaseWriter

from transcode.config.obj import Config

import pathlib
import os
import random
import io
from PIL import Image

icons = QFileIconProvider()


class AvailableAttachmentsNode(Node):
    def _wrapChildren(self, children):
        return InputFiles.fromValues(children, self)


class InputFiles(ChildNodes):
    @staticmethod
    def _wrap(value):
        return InputFileNode(value)


class InputFileNode(Node):
    def _iterChildren(self):
        if isinstance(self.value, MatroskaReader) and self.value.attachments:
            return self.value.attachments

        raise TypeError


class AvailableAttachmentsBaseColumn(object):
    checkstate = None
    fontmain = None
    fontalt = None
    fgcolor = None
    fgcoloralt = None
    bgcolor = None
    bgcoloralt = None
    name = None
    textalign = Qt.AlignLeft | Qt.AlignVCenter

    def __init__(self, input_files):
        self.input_files = input_files

    def flags(self, index, obj):
        if isinstance(obj, InputAttachedFile):
            return Qt.ItemIsEnabled | Qt.ItemIsSelectable

        return Qt.ItemIsEnabled


class AvailableAttachmentNameCol(AvailableAttachmentsBaseColumn):
    headerdisplay = "Attachment"
    width = 192

    def display(self, index, obj):
        if isinstance(obj, BaseReader):
            return f"{self.input_files.index(obj)}: {obj.inputpathrel}"

        elif isinstance(obj, InputAttachedFile):
            return f"{obj.parent.attachedFiles.index(obj)}: {obj.fileName}"

    tooltip = display

    def icon(self, index, obj):
        if isinstance(obj, BaseReader):
            return icons.icon(QFileInfo(obj.inputpathrel))

        elif isinstance(obj, InputAttachedFile):
            return icons.icon(QFileInfo(obj.fileName))


class AvailableAttachmentSizeCol(AvailableAttachmentsBaseColumn):
    headerdisplay = "File Size"
    width = 96

    def display(self, index, obj):
        if isinstance(obj, InputAttachedFile):
            size = obj.fileData.size

            if size >= 1024**4:
                return f"{size/1024**4:,.2f} TB"

            elif size >= 1024**3:
                return f"{size/1024**3:,.2f} GB"

            elif size >= 1024**2:
                return f"{size/1024**2:,.2f} MB"

            elif size >= 1024:
                return f"{size/1024:,.2f} KB"

            return f"{size:,} B"

        return ""


class AvailableAttachmentMimeTypeCol(AvailableAttachmentsBaseColumn):
    headerdisplay = "Mime Type"
    width = 96

    def display(self, index, obj):
        if isinstance(obj, InputAttachedFile):
            return obj.mimeType

        return ""

    tooltip = display


class AvailableAttachmentUIDCol(AvailableAttachmentsBaseColumn):
    headerdisplay = "UID"
    width = 96

    def display(self, index, obj):
        if isinstance(obj, InputAttachedFile):
            c, d = divmod(obj.fileUID, 16**4)
            b, c = divmod(c, 16**4)
            a, b = divmod(b, 16**4)

            return f"{a:04x} {b:04x} {c:04x} {d:04x}"

        return ""


class AvailableAttachmentDescriptionCol(AvailableAttachmentsBaseColumn):
    headerdisplay = "Description"
    width = 128

    def display(self, index, obj):
        if isinstance(obj, InputAttachedFile):
            return obj.description or ""

        return ""


class AvailableAttachmentsTree(QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setSelectionMode(QTreeView.ExtendedSelection)
        self.setInputFiles(None)
        self.setMinimumWidth(640)

    def setInputFiles(self, input_files):
        self.input_files = input_files

        if input_files is not None:
            root = AvailableAttachmentsNode(input_files)
            cols = [
                AvailableAttachmentNameCol(input_files),
                AvailableAttachmentSizeCol(input_files),
                AvailableAttachmentMimeTypeCol(input_files),
                AvailableAttachmentUIDCol(input_files),
                AvailableAttachmentDescriptionCol(input_files),
            ]
            model = QItemModel(root, cols)
            self.setModel(model)

            for k, col in enumerate(cols):
                if hasattr(col, "width") and isinstance(col.width, int):
                    self.setColumnWidth(k, col.width)

                if hasattr(col, "itemDelegate") and callable(col.itemDelegate):
                    self.setItemDelegateForColumn(k, col.itemDelegate(self))

            self.expandAll()

        else:
            self.setModel(QItemModel(Node(None), []))


class AvailableAttachmentsSelection(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)

        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        self.selectionTree = AvailableAttachmentsTree(self)
        self.selectionTree.setMinimumHeight(240)
        self.previewWidget = QImageView(self)
        self.previewWidget.setMinimumWidth(240)
        self.previewWidget.setMaximumWidth(360)
        self.previewWidget.hide()
        hlayout.addWidget(self.selectionTree)
        hlayout.addWidget(self.previewWidget)

        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        self.okayBtn = QPushButton("&OK", self)
        self.cancelBtn = QPushButton("&Cancel", self)

        hlayout.addStretch()
        hlayout.addWidget(self.okayBtn)
        hlayout.addWidget(self.cancelBtn)

        self.okayBtn.clicked.connect(self.applyAndClose)
        self.cancelBtn.clicked.connect(self.close)
        self.selectedAttachments = None

    def handleSelectionChanged(self):
        self.okayBtn.setEnabled(
            len(self.selectionTree.selectionModel().selectedRows()) > 0)

        selected = self.selectionTree.currentIndex().data(Qt.UserRole)

        if selected.mimeType in ("image/jpeg", "image/png"):
            try:
                with io.BytesIO() as b:
                    b.write(b"".join(selected.fileData))
                    b.seek(0)
                    im = Image.open(b).copy()

            except:
                self.previewWidget.hide()
                return

            self.previewWidget.setFrame(im.toqpixmap())
            self.previewWidget.show()

        else:
            self.previewWidget.hide()

    def applyAndClose(self):
        self.selectedAttachments = [
            (index.parent().data(Qt.UserRole), index.data(Qt.UserRole))
            for index in self.selectionTree.selectionModel().selectedRows()
        ]
        self.done(1)
        self.close()

    def setInputFiles(self, input_files):
        self.selectionTree.setInputFiles(input_files)
        self.selectionTree.selectionModel().selectionChanged.connect(
            self.handleSelectionChanged)
        self.okayBtn.setEnabled(len(self.selectionTree.selectedIndexes()) > 0)


class AttachmentModel(QItemModel):
    def dropItems(self, items, action, row, column, parent):
        if row == -1:
            row = self.rowCount(parent)

        node = self.getNode(parent)

        j = 0

        for k, item in enumerate(items):
            old_parent = self.findIndex(item.parent)
            old_row = item.parent.index(item)
            self.moveRow(old_row, row + k - j, old_parent, parent)

            if self.getNode(old_parent) is self.getNode(parent) and old_row < row:
                j += 1

            return False

        return True

    def canDropUrls(self, urls, action, row, column, parent):
        workingdir = self.root.value.parent.config.workingdir

        if parent.isValid():
            return False

        for url in urls:
            if url.scheme() != "file":
                return False

            if not os.path.isfile(url.path()):
                return False

            fileName = os.path.relpath(url.path(), workingdir)
            path, fileStem = os.path.split(fileName)

        return True

    def dropUrls(self, urls, action, row, column, parent):
        workingdir = self.root.value.parent.config.workingdir
        existingUIDs = {node.value.UID for node in self.root.children}

        if row == -1:
            row = self.rowCount(parent)

        k = 0
        newfiles = []

        for url in urls:
            UID = random.randint(1, 2**64 - 1)

            while UID in existingUIDs:
                UID = random.randint(1, 2**64 - 1)

            relPath = os.path.relpath(url.path(), workingdir)

            if relPath.startswith(f"{os.path.pardir}{os.path.sep}"):
                fileName = url.path()

            else:
                fileName = relPath

            _, fileStem = os.path.split(fileName)
            newfiles.append(AttachedFile(
                UID, source=fileName, fileName=fileStem))
            existingUIDs.add(UID)

        self.insertRows(row, newfiles, parent)
        return True

    def canDropItems(self, items, action, row, column, parent):
        node = self.getNode(parent)

        for item in items:
            o = item

            while o.parent is not None:
                o = o.parent

            if o is not self.root:
                return False

        return True

    def supportedDragActions(self):
        return Qt.MoveAction

    def supportedDropActions(self):
        return Qt.MoveAction | Qt.CopyAction


class AttachmentsNode(Node):
    def _wrapChildren(self, children):
        return AttachmentsChildren.fromValues(children, self)


class AttachmentsChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return AttachmentNode(value)


class AttachmentNode(NoChildren):
    pass


class BaseColumn(object):
    checkstate = None
    fontmain = None
    fontalt = None
    fgcolor = None
    fgcoloralt = None
    bgcolor = None
    bgcoloralt = None
    name = None
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
    textalign = Qt.AlignLeft | Qt.AlignVCenter

    def __init__(self, tags, attachments, attrname):
        self.tags = tags
        self.attachments = attachments
        self.attrname = attrname

    def editdata(self, index, obj):
        return getattr(obj, self.attrname)

    def seteditdata(self, index, obj, data):
        try:
            setattr(obj, self.attrname, data)

        except:
            return False

        return True

    def display(self, index, obj):
        return str(self.editdata(index, obj))

    def font(self, index, obj):
        return self.fontmain

    def bgdata(self, index, obj):
        return self.bgcolor

    def fgdata(self, index, obj):
        return self.fgcolor

    def contextmenu(self, index, obj):
        return partial(self.createContextMenu, obj=obj, index=index)

    def createContextMenu(self, table, index, obj):
        menu = QMenu(table)

        addFromFile = QAction("&Add attachment(s) from file(s)...", table,
                              triggered=table.addFromFile)
        menu.addAction(addFromFile)

        addFromInput = QAction("&Import existing attachment(s) from input...", table,
                               triggered=table.addFromInput)
        menu.addAction(addFromInput)

        removeSelected = QAction("&Remove selected attachment(s)...", table,
                                 triggered=table.askDeleteSelected)
        menu.addAction(removeSelected)

        return menu

    def flags(self, index, obj):
        if isinstance(obj, SimpleTag):
            return Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

        return Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled


class NameCol(BaseColumn):
    width = 128
    headerdisplay = "Attachment"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, tags, attachments):
        super().__init__(tags, attachments, "fileName")

    def display(self, index, obj):
        return f"{self.attachments.index(obj)}: {obj.fileName}"

    def icon(self, index, obj):
        return icons.icon(QFileInfo(obj.fileName))


class SizeCol(BaseColumn):
    width = 128
    headerdisplay = "Size"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, tags, attachments):
        super().__init__(tags, attachments, None)

    def display(self, index, obj):
        workingdir = obj.parent.config.workingdir

        if isinstance(obj.source, AttachmentRef):
            size = obj.source.attachment.fileData.size

        else:
            size = os.stat(obj.sourceabs).st_size

        if size >= 1024**4:
            return f"{size/1024**4:,.2f} TB"

        elif size >= 1024**3:
            return f"{size/1024**3:,.2f} GB"

        elif size >= 1024**2:
            return f"{size/1024**2:,.2f} MB"

        elif size >= 1024:
            return f"{size/1024:,.2f} KB"

        return f"{size:,} B"


class SourceCol(BaseColumn):
    width = 128
    headerdisplay = "Source"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, tags, attachments):
        super().__init__(tags, attachments, "source")

    def display(self, index, obj):
        config = self.attachments.parent.config
        input_files = config.input_files
        data = self.editdata(index, obj)

        if isinstance(data, AttachmentRef):
            return f"Attachment {data.UID} from input:{input_files.index(data.source)} ({data.source.inputpathrel})"

        return obj.sourcerel

    def tooltip(self, index, obj):
        return str(self.editdata(index, obj))


class MimeTypeCol(BaseColumn):
    width = 128
    headerdisplay = "Mime Type"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, tags, attachments):
        super().__init__(tags, attachments, "mimeType")

    # def display(self, index, obj):
        # return f"{obj.parent.attachments.index(obj)}: {obj.fileName}"


class UIDCol(BaseColumn):
    width = 256
    headerdisplay = "UID"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, tags, attachments):
        super().__init__(tags, attachments, "UID")

    # def display(self, index, obj):
        # return f"0x{int(self.editdata(index, obj)):032x}"

    def display(self, index, obj):
        c, d = divmod(self.editdata(index, obj), 16**4)
        b, c = divmod(c, 16**4)
        a, b = divmod(b, 16**4)

        return f"{a:04x} {b:04x} {c:04x} {d:04x}"

    def itemDelegate(self, parent):
        return UIDDelegate(parent)

    def contextmenu(self, index, obj):
        return partial(self.createContextMenu, obj=obj, index=index)

    def createContextMenu(self, table, index, obj):
        menu = super().createContextMenu(table, index, obj)
        selectRandom = QAction(f"Select random UID", table,
                             triggered=partial(self.selectRandomUID, obj, table.model()))

        menu.addAction(selectRandom)
        return menu

    def selectRandomUID(self, obj, model):
        UID = random.randint(1, 2**64 - 1)

        existingUIDs = {attachment.UID for attachment in self.attachments if attachment is not obj}

        while UID in existingUIDs:
            UID = random.randint(1, 2**64 - 1)

        obj.UID = UID
        model.dataChanged.emit(QModelIndex(), QModelIndex())


class DescriptionCol(BaseColumn):
    width = 256
    headerdisplay = "Description"
    flags = Qt.ItemIsSelectable | Qt.ItemIsEditable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled

    def __init__(self, tags, attachments):
        super().__init__(tags, attachments, "description")

    def display(self, index, obj):
        data = self.editdata(index, obj)
        return data or ""

    def seteditdata(self, index, obj, value):
        super().seteditdata(index, obj, value or None)


class QAttachmentTree(QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumWidth(640)
        self.setDragDropMode(QTreeView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setSelectionMode(QTreeView.ExtendedSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setData(None, None)

        self.setSelectionBehavior(QAbstractItemView.SelectRows)

    def contextMenuEvent(self, event):
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.mapToGlobal(event.pos()))

    def setData(self, tags, attachments):
        self.tags = tags
        self.attachments = attachments

        if self.attachments is not None:
            cols = [
                NameCol(tags, attachments),
                SourceCol(tags, attachments),
                SizeCol(tags, attachments),
                MimeTypeCol(tags, attachments),
                UIDCol(tags, attachments),
                DescriptionCol(tags, attachments),
            ]

            root = AttachmentsNode(attachments)
            model = AttachmentModel(root, cols)
            self.setModel(model)

            for k, col in enumerate(cols):
                if hasattr(col, "width") and isinstance(col.width, int):
                    self.setColumnWidth(k, col.width)

                if hasattr(col, "itemDelegate") and callable(col.itemDelegate):
                    self.setItemDelegateForColumn(k, col.itemDelegate(self))

        else:
            self.setModel(QItemModel(Node(None), []))

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()
        idx = self.currentIndex()
        row = idx.row()
        col = idx.column()
        model = self.model()

        selected = sorted(idx.row()
                          for idx in self.selectionModel().selectedRows())

        if key == Qt.Key_Delete and modifiers == Qt.NoModifier and len(self.selectionModel().selectedRows()):
            self.askDeleteSelected()

        super().keyPressEvent(event)

    def askDeleteSelected(self):
        answer = QMessageBox.question(
            self, "Delete attachment(s)", "Do you wish to delete the selected attachment(s)?", QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:
            self.deleteSelected()

    def deleteSelected(self):
        model = self.model()
        selected = {model.getNode(index) for index in self.selectedIndexes()}
        removed = set()

        for node in selected:
            parent = node.parent

            if node not in removed:
                model.removeRow(parent.index(node), model.findIndex(parent))
                removed.add(node)

                if node.descendants is not None:
                    removed.update(node.descendants)

    def addFromFile(self):
        if (isinstance(self.attachments, Attachments)
            and isinstance(self.attachments.parent, BaseWriter)
            and isinstance(self.attachments.parent.config, Config)):
            path = os.path.abspath(self.attachments.parent.config.workingdir)

        else:
            path = None

        existingUIDs = {attachment.UID for attachment in self.attachments}
        filters = "All image files (*.jpg *.png *.);;All files (*)"
        fileNames, _ = QFileDialog.getOpenFileNames(self, "Add attachments...",
                                                    path, filters)
        newfiles = []

        for fileName in fileNames:
            UID = random.randint(1, 2**64 - 1)

            while UID in existingUIDs:
                UID = random.randint(1, 2**64 - 1)

            _, fileStem = os.path.split(fileName)
            newfiles.append(AttachedFile(
                UID, source=fileName, fileName=fileStem))
            existingUIDs.add(UID)

        self.model().insertRows(self.model().rowCount(), newfiles)

    def addFromInput(self):
        dlg = AvailableAttachmentsSelection(self)
        dlg.setInputFiles(self.attachments.parent.config.input_files)
        existingUIDs = {attachment.UID for attachment in self.attachments}

        if dlg.exec_():
            model = self.model()
            newfiles = []

            for (input_file, attachment) in dlg.selectedAttachments:
                UID = attachment.fileUID
                source = AttachmentRef(input_file, UID)

                while UID in existingUIDs:
                    UID = random.randint(1, 2**64 - 1)

                newfiles.append(AttachedFile(UID, source=source,
                                             fileName=attachment.fileName, mimeType=attachment.mimeType,
                                             description=attachment.description))
                existingUIDs.add(UID)

            model.insertRows(model.rowCount(), newfiles, QModelIndex())


class QAttachmentsWidget(QWidget):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)

        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)

        self.attachTree = QAttachmentTree(self)
        self.attachTree.setMinimumHeight(240)
        hlayout.addWidget(self.attachTree)
        self.previewWidget = QImageView(self)
        self.previewWidget.setMinimumWidth(240)
        self.previewWidget.setMaximumWidth(360)
        self.previewWidget.hide()
        hlayout.addWidget(self.previewWidget)

        btnlayout = QHBoxLayout()
        layout.addLayout(btnlayout)

        self.add1Btn = QPushButton("&Add attachment(s) from file(s)...", self)
        self.add2Btn = QPushButton(
            "&Import existing attachment(s) from input...", self)
        self.removeBtn = QPushButton("&Remove selected attachment(s)", self)
        self.add1Btn.clicked.connect(self.attachTree.addFromFile)
        self.add2Btn.clicked.connect(self.attachTree.addFromInput)
        self.removeBtn.clicked.connect(self.attachTree.askDeleteSelected)


        btnlayout.addWidget(self.add1Btn)
        btnlayout.addWidget(self.add2Btn)
        btnlayout.addWidget(self.removeBtn)
        btnlayout.addStretch()

    def setData(self, tags, attachments):
        self.attachTree.setData(tags, attachments)

        if attachments is not None:
            self.attachTree.model().dataChanged.connect(self.contentsModified)
            self.attachTree.model().rowsInserted.connect(self.contentsModified)
            self.attachTree.model().rowsRemoved.connect(self.contentsModified)
            self.attachTree.model().rowsMoved.connect(self.contentsModified)
            self.attachTree.selectionModel().selectionChanged.connect(
                self.handleSelectionChanged)
            self.handleSelectionChanged()

    def handleSelectionChanged(self):
        self.removeBtn.setEnabled(
            len(self.attachTree.selectionModel().selectedRows()) > 0)

        selected = self.attachTree.currentIndex().data(Qt.UserRole)

        if isinstance(selected, AttachedFile) and selected.mimeType in ("image/jpeg", "image/png"):
            try:
                if isinstance(selected.source, AttachmentRef):
                    with io.BytesIO() as b:
                        b.write(b"".join(selected.source.attachment.fileData))
                        b.seek(0)
                        im = Image.open(b).copy()


                else:
                    im = Image.open(selected.source)

            except:
                self.previewWidget.hide()
                return

            self.previewWidget.setFrame(im.toqpixmap())
            self.previewWidget.show()

        else:
            self.previewWidget.hide()
