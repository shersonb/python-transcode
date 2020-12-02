from PyQt5.QtCore import (Qt, pyqtSignal)
from PyQt5.QtWidgets import (QTreeView, QMenu)
from .treeview import TreeView as QTreeView
from .qitemmodel import QItemModel, Node
import sys

from .qinputselection import InputDelegate
from .qfilterlistmodel import FilterListModel, FiltersRoot
from .qfilterlistcols import FilterNameCol, SourceCol, OptionsCol, FormatCol, DurationCol


class EditableSourceCol(SourceCol):
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled | Qt.ItemIsEditable

    def itemDelegate(self, parent):
        return InputDelegate(self.filters.config.input_files, self.filters, parent)


class QFilterList(QTreeView):
    contentsModified = pyqtSignal()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimumWidth(640)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeView.DragDrop)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropOverwriteMode(True)
        self.setDropIndicatorShown(True)
        self.setFilters(None)

    def setFilters(self, filters):
        self.filters = filters

        if filters is not None:
            cols = [
                FilterNameCol(filters),
                EditableSourceCol(filters),
                FormatCol(filters),
                DurationCol(filters),
                OptionsCol(filters),
            ]

            self.setModel(FilterListModel(FiltersRoot(filters), cols))
            #self.model().dataChanged.connect(self.contentsModified)
            #self.model().rowsMoved.connect(self.contentsModified)
            #self.model().rowsInserted.connect(self.contentsModified)
            #self.model().rowsRemoved.connect(self.contentsModified)

            for k, col in enumerate(cols):
                if hasattr(col, "width"):
                    self.setColumnWidth(k, col.width)

                if callable(col.itemDelegate):
                    self.setItemDelegateForColumn(k, col.itemDelegate(self))

        else:
            self.setModel(QItemModel(Node(None), []))

    #def contextMenuEvent(self, event):
        #selected = self.currentIndex()
        #menu = self.model().data(selected, role=Qt.UserRole + 1)

        #if callable(menu):
            #menu = menu(self)

        #if isinstance(menu, QMenu):
            #menu.exec_(self.mapToGlobal(event.pos()))


