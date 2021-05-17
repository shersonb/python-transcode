from PyQt5.QtCore import Qt, QModelIndex, pyqtSignal, QFileInfo
from PyQt5.QtGui import QFont, QBrush, QColor, QPainter
from PyQt5.QtWidgets import (QTreeView, QAbstractItemView, QWidget, QVBoxLayout,
                             QMenu, QAction, QMessageBox, QFileIconProvider, QToolButton,
                             QWidgetAction, QLabel, QHBoxLayout)

from .qitemmodel import QItemModel, Node
from .treeview import TreeView as QTreeView
from transcode.containers import writers
from functools import partial

icons = QFileIconProvider()


class OutputFilesRoot(Node):
    def canDropChildren(self, model, parent, items, row, action):
        if action == Qt.CopyAction:
            return False

        elif action == Qt.MoveAction:
            for item in items:
                if item not in self.children:
                    return False

        return True

    def dropChildren(self, model, parent, items, row, action):
        j = 0

        for k, item in enumerate(items, row):
            old_row = self.children.index(item)
            model.moveRow(old_row, k - j, parent)

            if old_row < row:
                j += 1

        return True

    def canDropItems(self, model, parent, items, action):
        return self.canDropChildren(model, parent, items, len(self.children), action)

    def dropItems(self, model, parent, items, action):
        return self.dropChildren(model, parent, items, len(self.children), action)



class OutputFilesModel(QItemModel):
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
                           table, triggered=partial(table.addFile, cls=writer))
            newAtBottomSubMenu.addAction(item)

            item = QAction(f"{writer.fmtname} ({', '.join(writer.extensions)}) [{clsname[len('transcode.containers.'):]}]",
                           table, triggered=partial(table.addFile, cls=writer, row_id=index.row()))
            insertSubMenu.addAction(item)

        delete = QAction("Delete selected...",
                         table, triggered=partial(table.askDeleteSelected))

        if len(table.selectedIndexes()) == 0:
            delete.setDisabled(True)

        menu.addAction(delete)
        return menu


class QOutputFileList(QTreeView):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setFont(QFont("DejaVu Serif", 8))
        self.setMinimumWidth(256)

        self.setDragDropMode(QTreeView.DragDrop)
        self.setDefaultDropAction(Qt.MoveAction)

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

            self.setModel(OutputFilesModel(OutputFilesRoot(output_files), cols))
            #self.model().dataChanged.connect(self.contentsModified)
            #self.model().rowsInserted.connect(self.contentsModified)
            #self.model().rowsMoved.connect(self.contentsModified)
            #self.model().rowsRemoved.connect(self.contentsModified)

            for k, col in enumerate(cols):
                if hasattr(col, "width"):
                    self.setColumnWidth(k, col.width)

                if callable(col.itemDelegate):
                    self.setItemDelegateForColumn(k, col.itemDelegate(self))

        else:
            self.setModel(QItemModel(Node(None), []))

    def askDeleteSelected(self):
        model = self.model()
        selected = {model.getNode(index)
                    for index in self.selectedIndexes()}

        if len(selected) == 1:
            answer = QMessageBox.question(self, "Confirm delete output file",
                                          "Do you wish to delete the selected output file?", QMessageBox.Yes | QMessageBox.No)

        elif len(selected) > 1:
            answer = QMessageBox.question(self, "Confirm delete output files",
                                          "Do you wish to delete the selected output files?", QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:
            self.deleteSelected()

    def addFile(self, cls, row_id=-1):
        model = self.model()

        if row_id == -1:
            row_id = model.rowCount(QModelIndex())

        ext = cls.extensions[0]
        filename = f"untitled{ext}"
        output_file = cls(filename, tracks=[])
        model.insertRow(row_id, output_file, QModelIndex())
        self.setCurrentIndex(model.index(row_id, 0, QModelIndex()))


class QOutputFiles(QWidget):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.outputFileList = QOutputFileList(self)
        layout.addWidget(self.outputFileList)
        self.outputFileList.contentsModified.connect(self.contentsModified)

        btnlayout = QHBoxLayout()
        layout.addLayout(btnlayout)

        self.addBtn = QToolButton(self)
        self.addBtn.setText("Add output file")
        self.addBtn.setPopupMode(QToolButton.MenuButtonPopup)
        self.addBtn.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)
        self.addBtn.clicked.connect(self.addBtn.showMenu)

        addMenu = QMenu(self.addBtn)
        self.addBtn.setMenu(addMenu)

        for clsname, writer in sorted(writers.items()):
            item = QAction(f"{writer.fmtname} ({', '.join(writer.extensions)}) [{clsname[len('transcode.containers.'):]}]",
                           self, triggered=partial(self.outputFileList.addFile, cls=writer))
            addMenu.addAction(item)

        btnlayout.addWidget(self.addBtn)

    def setOutputFiles(self, output_files):
        self.outputFileList.setOutputFiles(output_files)
