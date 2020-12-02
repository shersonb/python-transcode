from PyQt5.QtWidgets import QTreeView, QMenu
from PyQt5.QtCore import Qt, pyqtSignal
import gc

class TreeView(QTreeView):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.openContextMenu)

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        supp = self.model().supportedDropActions()
        mod = event.keyboardModifiers()

        if mod == Qt.NoModifier and supp & Qt.MoveAction and supp & Qt.CopyAction:
            if event.source() is self:
                #Internal MOVE
                event.setDropAction(Qt.MoveAction)

            else:
                #Everything else is assumed to be COPY
                event.setDropAction(Qt.CopyAction)

            event.accept()

    def openContextMenu(self, pos):
        print("openContextMenu", self, pos)
        selected = self.currentIndex()
        menu = self.model().data(selected, role=Qt.UserRole + 1)

        if callable(menu):
            menu = menu(self)

        if isinstance(menu, QMenu):
            menu.exec_(self.viewport().mapToGlobal(pos))

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

        print("Garbage Collection", gc.collect())

    def setModel(self, model):
        super().setModel(model)
        model.dataChanged.connect(self.contentsModified)
        model.rowsInserted.connect(self.contentsModified)
        model.rowsMoved.connect(self.contentsModified)
        model.rowsRemoved.connect(self.contentsModified)

