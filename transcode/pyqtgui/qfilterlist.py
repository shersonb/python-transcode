from PyQt5.QtCore import (Qt, pyqtSignal)
from .treeview import TreeView as QTreeView
from .qitemmodel import QItemModel, Node

from .qinputselection import InputDelegate
from .qfilterlistmodel import FilterListModel, FiltersRoot
from .qfilterlistcols import (FilterNameCol, SourceCol, OptionsCol,
                              FormatCol, DurationCol)


class EditableSourceCol(SourceCol):
    flags = (Qt.ItemIsSelectable | Qt.ItemIsEnabled
             | Qt.ItemIsDragEnabled | Qt.ItemIsEditable)

    def itemDelegate(self, parent):
        return InputDelegate(self.filters.config.input_files,
                             self.filters, parent)


class QFilterList(QTreeView):
    contentsModified = pyqtSignal()
    _deletetitle = "Confirm delete filter(s)"
    _deletemsg = "Do you wish to delete the selected filter(s)? "\
        "All references to selected filter(s) will be broken."

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

        else:
            self.setModel(QItemModel(Node(None), []))
