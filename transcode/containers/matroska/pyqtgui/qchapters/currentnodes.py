from transcode.pyqtgui.qitemmodel import Node, ChildNodes, NoChildren

from matroska.chapters import ChapterAtom as InputChapterAtom
from matroska.chapters import ChapterDisplay as InputChapterDisplay


class EditionsNode(Node):
    def _wrapChildren(self, children):
        return EditionsChildren.fromValues(children, self)


class EditionsChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return EditionNode(value)


class EditionNode(Node):
    def _wrapChildren(self, children):
        return EditionChildren.fromValues(children, self)


class EditionChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return ChapterNode(value)


class ChapterNode(Node):
    def _iterChildren(self):
        return self.value.displays

    def _wrapChildren(self, children):
        return ChapterChildren.fromValues(children, self)


class ChapterChildren(ChildNodes):
    @staticmethod
    def _wrap(value):
        return DisplayNode(value)

    def _append(self, value):
        self.parent.value.displays.append(node.value)

    def _insert(self, index, value):
        self.parent.value.displays.insert(index, value)

    def _extend(self, values):
        self.parent.value.displays.extend(values)

    def _delitem(self, index):
        del self.parent.value.displays[index]

    def _setitem(self, index, value):
        self.parent.value.displays[index] = value


class DisplayNode(NoChildren):
    pass

