from PyQt5.QtCore import Qt, QAbstractItemModel, QModelIndex
from PyQt5.QtGui import QFont, QIcon, QBrush, QPen
from PyQt5.QtWidgets import QTreeView, QAbstractItemView, QWidget, QHBoxLayout, QVBoxLayout, QMenu, QAction

from .qobjectitemmodel import QObjectItemModel
from transcode.containers import writers
from functools import partial

class OutputFilesModel(QObjectItemModel):
    def parentObject(self, obj):
        return self.items

    def getItems(self, parent):
        if parent.isValid():
            return None

        return self.items

    def dropItems(self, items, action, row, column, parent):
        if parent.isValid():
            return False

        if row == -1:
            row = self.rowCount(parent)

        j = 0

        for k, item in enumerate(items):
            if item in self.items and action == Qt.MoveAction:
                old_row = self.items.index(item)
                self.moveRow(old_row, row + k - j, parent, parent)

                if old_row < row:
                    j += 1

        return True

    def canDropItems(self, items, action, row, column, parent):
        for item in items:
            if item not in self.items:
                return False

        return

    def supportedDropActions(self):
        return Qt.MoveAction

class OutputFileCol(object):
    headerdisplay = "File"
    font = QFont("DejaVu Serif", 8)
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsDropEnabled
    textalign = Qt.AlignLeft | Qt.AlignVCenter
    bgdata = QBrush()
    itemDelegate = None

    def __init__(self, output_files):
        self.output_files = output_files

    def display(self, index, obj):
        return f"{self.output_files.index(obj)}: {obj.outputpathrel}"

    tooltip = display

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

        return menu

    def addFile(self, table, model, cls, row_id=-1):
        if row_id == -1:
            row_id = model.rowCount(QModelIndex())

        ext = cls.extensions[0]
        filename = f"untitled{ext}"
        output_file = cls(filename, tracks=[])
        model.insertRow(row_id, output_file, QModelIndex())

class QOutputFileList(QTreeView):
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

            self.setModel(OutputFilesModel(output_files, cols))
            self.model().dataChanged.connect(self.contentsChanged)

            for k, col in enumerate(cols):
                if hasattr(col, "width"):
                    self.setColumnWidth(k, col.width)

                if callable(col.itemDelegate):
                    self.setItemDelegateForColumn(k, col.itemDelegate(self))

        else:
            self.setModel(QObjectItemModel([], []))

    def contentsChanged(self, idx1, idx2):
        pass

    def contextMenuEvent(self, event):
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.mapToGlobal(event.pos()))

class QOutputFiles(QWidget):
    def __init__(self, output_files=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.outputFileList = QOutputFileList(output_files, self)
        layout.addWidget(self.outputFileList)
