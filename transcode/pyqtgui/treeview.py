from PyQt5.QtWidgets import QTreeView, QMenu, QMessageBox
from PyQt5.QtCore import Qt, pyqtSignal, pyqtBoundSignal
import gc
import traceback
import sys


class TreeView(QTreeView):
    contentsModified = pyqtSignal()
    _deletetitle = "Delete items"
    _deletemsg = "Do you wish to delete the selected items?"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setMinimumHeight(160)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.openContextMenu)
        self.setSelectionBehavior(QTreeView.SelectRows)
        self.setSelectionMode(QTreeView.ExtendedSelection)

    def _getDropAction(self, event):
        supp = self.model().supportedDropActions()
        mod = event.keyboardModifiers()
        internaldrag = event.source() is self
        default = self.defaultDropAction()

        if (mod == Qt.NoModifier
                and supp & Qt.MoveAction
                and supp & Qt.CopyAction):
            if internaldrag:
                return Qt.MoveAction

            else:
                return Qt.CopyAction

        elif mod == Qt.ControlModifier and supp & Qt.CopyAction:
            return Qt.CopyAction

        elif mod == Qt.ShiftModifier and supp & Qt.MoveAction:
            return Qt.MoveAction

        else:
            return default

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        action = self._getDropAction(event)

        if self._canDrop(event):
            event.setDropAction(action)
            event.accept()

        else:
            event.ignore()

    def dropEvent(self, event):
        if self._canDrop(event):
            self._drop(event)

    def _getDropArgs(self, event):
        droppos = self.dropIndicatorPosition()
        mimeData = event.mimeData()
        pos = event.pos()
        index = self.indexAt(pos)
        col = index.column()

        if droppos == QTreeView.AboveItem:
            parent = index.parent()
            row = index.row()

        elif droppos == QTreeView.BelowItem:
            parent = index.parent()
            row = index.row() + 1

        elif droppos == QTreeView.OnItem:
            parent = index
            row = -1

        else:
            parent = self.model().index(0, 0).parent()
            row = -1

        return (mimeData, row, col, parent)

    def _canDrop(self, event):
        (data, row, column, parent) = self._getDropArgs(event)
        action = self._getDropAction(event)
        return self.model().canDropMimeData(data, action, row, column, parent)

    def _drop(self, event):
        (data, row, column, parent) = self._getDropArgs(event)
        action = self._getDropAction(event)
        return self.model().dropMimeData(data, action, row, column, parent)

    def openContextMenu(self, pos):
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.viewport().mapToGlobal(pos))

    def keyPressEvent(self, event):
        key = event.key()
        modifiers = event.modifiers()

        if (key == Qt.Key_Delete
                and modifiers == Qt.NoModifier
                and len(self.selectionModel().selectedRows())):
            self.askDeleteSelected()

        super().keyPressEvent(event)

    def askDeleteSelected(self):
        answer = QMessageBox.question(
            self, self._deletetitle, self._deletemsg,
            QMessageBox.Yes | QMessageBox.No)

        if answer == QMessageBox.Yes:
            self.deleteSelected()

    def deleteSelected(self):
        model = self.model()
        sm = self.selectionModel()
        selected = {model.getNode(index) for index in sm.selectedRows()}
        removed = set()

        for node in selected:
            parent = node.parent

            if node not in removed:
                model.removeRow(parent.index(node), model.findIndex(parent))
                removed.add(node)

                if node.descendants is not None:
                    removed.update(node.descendants)

        del removed
        gc.collect()

    def setModel(self, model):
        super().setModel(model)
        model.dataChanged.connect(self.contentsModified)
        model.rowsInserted.connect(self.contentsModified)
        model.rowsMoved.connect(self.contentsModified)
        model.rowsRemoved.connect(self.contentsModified)

        if hasattr(model, "columns"):
            for k, col in enumerate(model.columns):
                if hasattr(col, "width"):
                    self.setColumnWidth(k, col.width)

                if hasattr(col, "itemDelegate") and callable(col.itemDelegate):
                    delegate = col.itemDelegate(self)

                    if (hasattr(delegate, "contentsModified")
                        and isinstance(delegate.contentsModified,
                                       pyqtBoundSignal)):
                        delegate.contentsModified.connect(
                            self.contentsModified)

                    self.setItemDelegateForColumn(k, delegate)

    def _handleException(self, cls, exc, tb):
        print("".join(traceback.format_exception(cls, exc, tb)),
              file=sys.stderr, end="")
        excmsg = QMessageBox(self)
        excmsg.setWindowTitle(cls.__name__)
        excmsg.setText(str(exc))
        excmsg.setStandardButtons(QMessageBox.Ok)
        excmsg.setIcon(QMessageBox.Critical)
        excmsg.exec_()
