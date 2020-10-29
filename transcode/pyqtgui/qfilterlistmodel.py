from PyQt5.QtCore import Qt
from .qitemmodel import QItemModel, Node, ChildNodes, NoChildren


class FiltersRoot(Node):
    def _wrapChildren(self, children):
        return Filters.fromValues(children, self)

    def canDropChildren(self, model, index, items, row, action):
        if action == Qt.MoveAction:
            for item in items:
                if item not in self.children:
                    return False

        elif action == Qt.CopyAction:
            return False

        return True

    def dropChildren(self, model, index, items, row, action):
        model = index.model()

        if action == Qt.MoveAction:
            j = 0

            for k, item in enumerate(items, row):
                old_row = item.indexInParent
                model.moveRow(old_row, k - j, index, index)

                if old_row < row:
                    j += 1

        elif action == Qt.CopyAction:
            return False

        return True


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
