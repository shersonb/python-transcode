from PyQt5.QtCore import Qt
from .qitemmodel import QItemModel, Node, ChildNodes, NoChildren
from transcode.filters.base import BaseFilter


class FiltersRoot(Node):
    def _wrapChildren(self, children):
        return Filters.fromValues(children, self)

    def canDropChildren(self, model, index, items, row, action):
        if action == Qt.MoveAction:
            for item in items:
                if item not in self.children:
                    return False

        elif action == Qt.CopyAction:
            for item in items:
                if not isinstance(item.value, type) or \
                        not issubclass(item.value, BaseFilter):
                    return False

        return True

    def dropChildren(self, model, index, items, row, action):
        if action == Qt.MoveAction:
            j = 0

            for k, item in enumerate(items, row):
                old_row = item.indexInParent
                model.moveRow(old_row, k - j, index, index)

                if old_row < row:
                    j += 1

        elif action == Qt.CopyAction:
            for k, item in enumerate(items, row):
                model.insertRow(k, item.value(), index)

        return True

    def canDropItems(self, model, parent, items, action):
        return self.canDropChildren(model, parent,
                                    items, len(self.children), action)

    def dropItems(self, model, parent, items, action):
        return self.dropChildren(model, parent,
                                 items, len(self.children), action)


class Filters(ChildNodes):
    @staticmethod
    def _wrap(item):
        if hasattr(item, "makeNode") and callable(item.makeNode):
            return item.makeNode()

        return FilterNode(item)


class FilterNode(NoChildren):
    pass


class FilterListModel(QItemModel):
    def supportedDropActions(self):
        return Qt.MoveAction | Qt.CopyAction

    def supportedDragActions(self):
        return Qt.MoveAction | Qt.CopyAction
