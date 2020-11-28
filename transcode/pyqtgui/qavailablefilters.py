from .qitemmodel import QItemModel, Node
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTreeView)
from PyQt5.QtGui import QFont, QIcon



class AvailableFiltersModel(QItemModel):
    def canDragItems(self, *args):
        return True

    def supportedDragActions(self):
        return Qt.CopyAction


class AvailableFiltersCol(object):
    font = QFont("DejaVu Serif", 8)
    flags = Qt.ItemIsSelectable | Qt.ItemIsEnabled | Qt.ItemIsDragEnabled
    textalign = Qt.AlignLeft

    def display(self, index, obj):
        return obj.__name__

    def tooltip(self, index, obj):
        mod = ".".join(obj.__module__.split(".")[2:])

        if obj.__doc__:
            return f"{mod}.{obj.__name__}\n\n{obj.__doc__}"

        return f"{mod}.{obj.__name__}"


class AvailableFiltersListView(QTreeView):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setDragDropMode(QTreeView.DragOnly)
        self.setIndentation(0)
        self.setHeaderHidden(True)
        self.setAvailableFilters([])

    def setAvailableFilters(self, filters):
        root = Node(sorted(filters, key=lambda cls: cls.__name__))
        self.setModel(AvailableFiltersModel(root, [AvailableFiltersCol()]))


class QAvailableFilters(QWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        label = QLabel("Available Filters", self)
        label.setFont(QFont("DejaVu Serif", 14, QFont.Bold, italic=True))
        layout.addWidget(label)

        self.listView = AvailableFiltersListView(self)
        layout.addWidget(self.listView)

    def setAvailableFilters(self, filters):
        self.listView.setAvailableFilters(filters)


