from PyQt5.QtCore import Qt, QModelIndex, pyqtSignal, QFileInfo
from PyQt5.QtGui import QFont, QBrush
from PyQt5.QtWidgets import (QTreeView, QAbstractItemView, QWidget, QVBoxLayout,
                             QMenu, QAction, QMessageBox, QFileIconProvider)

from .qitemmodel import QItemModel, Node
from transcode.containers import writers
from functools import partial

icons = QFileIconProvider()


class OutputFilesModel(QItemModel):
    def dropItems(self, items, action, row, column, parent):
        node = self.getNode(parent)

        if row == -1:
            row = self.rowCount(parent)

        j = 0

        if action == Qt.MoveAction:
            for k, item in enumerate(items):
                old_row = node.children.index(item)
                self.moveRow(old_row, row + k - j, parent, parent)

                if old_row < row:
                    j += 1

        return True

    def canDropItems(self, items, action, row, column, parent):
        if parent.isValid():
            return False

        for item in items:
            if item not in self.root.children:
                return False

        return True

    def supportedDropActions(self):
        return Qt.MoveAction


class OutputFileCol(object):
    headerdisplay = "File"
    font = QFont("DejaVu Serif", 12, QFont.Bold, italic=True)
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled
    textalign = Qt.AlignLeft | Qt.AlignVCenter
    bgdata = QBrush()
    itemDelegate = None

    def __init__(self, output_files):
        self.output_files = output_files

    def display(self, index, obj):
        return f"{self.output_files.index(obj)}: {obj.outputpathrel}"

    tooltip = display

    def icon(self, index, obj):
        return icons.icon(QFileInfo(obj.outputpathrel))

    def contextmenu(self, index, obj):
        return partial(self.createContextMenu, obj=obj, index=index)

    def createContextMenu(self, table, index, obj):
        menu = QMenu(table)
        newAtBottomSubMenu = QMenu("&New File", table)
        insertSubMenu = QMenu("&Insert File", table)
        menu.addMenu(newAtBottomSubMenu)
        menu.addMenu(insertSubMenu)

        for clsname, writer in sorted(writers.items()):
            item = QAction(f"{writer.fmtname} ({', '.join(writer.extensions)}) [{clsname[len('transcode.containers.'):]}]",
                           table, triggered=partial(self.addFile, table=table, model=index.model(), cls=writer))
            newAtBottomSubMenu.addAction(item)

            item = QAction(f"{writer.fmtname} ({', '.join(writer.extensions)}) [{clsname[len('transcode.containers.'):]}]",
                           table, triggered=partial(self.addFile, table=table, model=index.model(), cls=writer, row_id=index.row()))
            insertSubMenu.addAction(item)

        delete = QAction("Delete selected...",
                         table, triggered=partial(self.deleteFile, table=table, model=index.model()))

        if len(table.selectedIndexes()) == 0:
            delete.setDisabled(True)

        menu.addAction(delete)
        return menu

    def deleteFile(self, table, model):
        selected = {index.data(Qt.UserRole)
                    for index in table.selectedIndexes()}

        if len(selected) == 1:
            answer = QMessageBox.question(table, "Confirm delete output file",
                                          "Do you wish to delete the selected output file?", QMessageBox.Yes | QMessageBox.No)

        elif len(selected) > 1:
            answer = QMessageBox.question(table, "Confirm delete output files",
                                          "Do you wish to delete the selected output files?", QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:

            for tag in selected.copy():
                index = model.findIndex(tag)

                if index.isValid():
                    model.removeRow(index.row(), index.parent())

    def addFile(self, table, model, cls, row_id=-1):
        if model is None:
            model = table.model()

        if row_id == -1:
            row_id = model.rowCount(QModelIndex())

        ext = cls.extensions[0]
        filename = f"untitled{ext}"
        output_file = cls(filename, tracks=[])
        model.insertRow(row_id, output_file, QModelIndex())
        table.setCurrentIndex(model.index(row_id, 0, QModelIndex()))


class QOutputFileList(QTreeView):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFont(QFont("DejaVu Serif", 8))
        self.setMinimumWidth(256)

        self.setDragDropMode(QTreeView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)

        self.setIndentation(0)
        self.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.setOutputFiles(None)

    def setOutputFiles(self, output_files=None):
        self.output_files = output_files

        if output_files is not None:
            cols = [
                OutputFileCol(output_files),
            ]

            self.setModel(OutputFilesModel(Node(output_files), cols))
            self.model().dataChanged.connect(self.contentsModified)

            for k, col in enumerate(cols):
                if hasattr(col, "width"):
                    self.setColumnWidth(k, col.width)

                if callable(col.itemDelegate):
                    self.setItemDelegateForColumn(k, col.itemDelegate(self))

        else:
            self.setModel(QItemModel(Node(None), []))

    def contextMenuEvent(self, event):
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.mapToGlobal(event.pos()))


class QOutputFiles(QWidget):
    contentsModified = pyqtSignal()

    def __init__(self, output_files=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.outputFileList = QOutputFileList(output_files, self)
        layout.addWidget(self.outputFileList)
        self.outputFileList.contentsModified.connect(self.contentsModified)
