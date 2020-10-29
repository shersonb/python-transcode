from PyQt5.QtCore import Qt, QItemSelectionModel
from PyQt5.QtGui import QColor, QFont
from itertools import count
from functools import partial
from fractions import Fraction as QQ
from PyQt5.QtWidgets import QMenu, QAction, QApplication, QAbstractItemView
from transcode.containers.basereader import Track


class BaseColumn(object):
    checkstate = None
    fontmain = None
    fontalt = None
    fgcolor = None
    fgcoloralt = None
    bgcolor = None
    bgcoloralt = None
    name = None
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable
    textalign = Qt.AlignLeft | Qt.AlignVCenter

    def __init__(self, attrname):
        self.attrname = attrname

    def display(self, index, obj):
        if hasattr(obj, self.attrname):
            return "%s" % getattr(obj, self.attrname)

    def font(self, index, obj):
        return self.fontmain

    def bgdata(self, index, obj):
        return self.bgcolor

    def fgdata(self, index, obj):
        return self.fgcolor

    def contextmenu(self, index, obj):
        return partial(self.createContextMenu, obj=obj, index=index)

    def createContextMenu(self, table, index, obj):
        return None


class FrameNumberCol(BaseColumn):
    headerdisplay = "Old #"
    width = 64

    def __init__(self, srcstream=None):
        self.srcstream = srcstream

    def display(self, index, obj):
        n = index.row()

        if isinstance(self.srcstream, Track) and self.srcstream.pts[n] in set(self.srcstream.index[:, 0]):
            return f"{index.row()} (K)"

        return f"{index.row()}"


class ZoneCol(BaseColumn):
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable

    def __init__(self, filter, zonestring="zone"):
        self.filter = filter
        self.zonestring = zonestring

    def display(self, index, obj):
        K, zone = self.filter.zoneAt(index.row())
        return "%s" % K

    def checkstate(self, index, obj):
        return index.row() in self.filter.zone_indices

    def setcheckstate(self, index, obj, data):
        if index == 0:
            return

        if self.checkstate(index, obj):
            self.filter.removeZoneAt(index.row())
            return True

        else:
            self.filter.insertZoneAt(index.row())
            return True

    def bgdata(self, index, obj):
        if index.row() in self.filter.zone_indices:
            return self.bgcolor

        return self.bgcoloralt

    def fgdata(self, index, obj):
        if index.row() in self.filter.zone_indices:
            return self.fgcolor

        return self.fgcoloralt

    def createContextMenu(self, table, index, obj):
        menu = QMenu(table)
        K, zone = self.filter.zoneAt(index.row())

        if index.row() == zone.src_start:
            prev_index = zone.prev.src_start if zone.prev is not None else None

        else:
            prev_index = zone.src_start

        next_index = zone.next.src_start if zone.next is not None else None

        move_to_prev = QAction(f"Move to &previous {self.zonestring}", table, triggered=partial(
            table.goto, row=prev_index))
        menu.addAction(move_to_prev)
        if prev_index is None:
            move_to_prev.setDisabled(True)

        move_to_next = QAction(f"Move to &next {self.zonestring}", table, triggered=partial(
            table.goto, row=next_index))
        menu.addAction(move_to_next)
        if next_index is None:
            move_to_next.setDisabled(True)

        menu.addSeparator()

        n = index.row()
        J, zone = self.filter.zoneAt(n)
        # {scene.src_start for scene in self.filter}
        zones = set(self.filter.zone_indices)
        thiszone = set(range(zone.src_start, zone.src_end))

        filterzones = QAction(f"&Show {self.zonestring} cuts", table, triggered=partial(
            self.setFilter, table=table, filter=zones))
        menu.addAction(filterzones)

        filterzones = QAction(f"&Show this {self.zonestring}", table, triggered=partial(
            self.setFilter, table=table, filter=thiszone))
        menu.addAction(filterzones)

        showall = QAction("Show &all rows", table,
                          triggered=partial(self.showAll, table=table))
        menu.addAction(showall)

        return menu

    def setFilter(self, table, filter=None):
        selected = table.model().mapToSource(table.currentIndex())
        n = selected.row()

        if isinstance(filter, (set, list, tuple)):
            S = {k for k in filter if k <= n}
            if len(S):
                m = max(S)
                selected = table.model().sourceModel().index(m, selected.column())

        table.model().setFilterFunc(filter)

        QApplication.processEvents()

        selected = table.model().mapFromSource(selected)

        if selected.isValid():
            sm = table.selectionModel()
            sm.setCurrentIndex(selected, QItemSelectionModel.Select)

            table.setCurrentIndex(selected)
            table.scrollTo(selected, QAbstractItemView.PositionAtCenter)

    def keypress(self, index, obj):
        return self._keyPressFunc

    def _keyPressFunc(self, table, event):
        return False

    def showAll(self, table):
        selected = table.model().mapToSource(table.currentIndex())

        table.model().setFilterFunc(None)
        QApplication.processEvents()

        #selected = table.currentIndex()
        selected = table.model().mapFromSource(selected)

        sm = table.selectionModel()
        sm.setCurrentIndex(selected, QItemSelectionModel.Select)

        table.setCurrentIndex(selected)
        table.scrollTo(selected, QAbstractItemView.PositionAtCenter)


class TimeStampCol(BaseColumn):
    headerdisplay = "Old PTS"
    width = 160
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def __init__(self, stream=None):
        self.stream = stream

    def display(self, index, obj):
        if self.stream is None:
            return "—"

        pts = self.stream.pts_time[index.row()]
        sgn = "-" if pts < 0 else ""
        m, s = divmod(abs(pts), 60)
        m = int(m)
        h, m = divmod(m, 60)
        return "%s%d:%02d:%06.3f (%.3f)" % (sgn, h, m, s, pts)


class NewTimeStampCol(BaseColumn):
    headerdisplay = "New PTS"
    width = 160
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def __init__(self, filter=None):
        self.filter = filter

    def display(self, index, obj):
        for m in count(index.row()):
            n = self.filter.cumulativeIndexMap[m]

            if n >= 0:
                break

            m += 1

        if n is not None and n >= 0:
            pts = self.filter.pts_time[n]

            sgn = "-" if pts < 0 else ""
            m, s = divmod(abs(pts), 60)
            m = int(m)
            h, m = divmod(m, 60)
            return "%s%d:%02d:%06.3f (%.3f)" % (sgn, h, m, s, pts)

        return "-"

    def fgdata(self, index, obj):
        try:
            if self.filter.cumulativeIndexMap[index.row()] >= 0:
                return QColor()
        except:
            return QColor(160, 160, 160)

        return QColor(160, 160, 160)


class NewFrameNumberCol(BaseColumn):
    headerdisplay = "New #"
    width = 64
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def __init__(self, filter=None):
        self.filter = filter

    def display(self, index, obj):
        for index in count(index.row()):
            try:
                n = self.filter.cumulativeIndexMap[index]

            except:
                return "ERR"

            if n is not None and n >= 0:
                return str(n)

        return "-"

    def fgdata(self, index, obj):
        try:
            if self.filter.cumulativeIndexMap[index.row()] >= 0:
                return QColor()

        except:
            return QColor(160, 160, 160)

        return QColor(160, 160, 160)


class DiffCol(BaseColumn):
    headerdisplay = "Diff"
    width = 64
    blue = QColor(0, 0, 255)
    white = QColor(255, 255, 255)
    red = QColor(255, 0, 0)
    bold = QFont(None)
    flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

    def __init__(self, filter=None):
        self.filter = filter

    def display(self, index, obj):
        diff = self.editdata(index, obj)

        if diff is not None:
            return "%.3f" % diff

        return "-"

    def editdata(self, index, obj):
        n = self.filter.cumulativeIndexMap[index.row()]

        if n is not None and n >= 0:
            new_pts = self.filter.pts_time[n]
            old_pts = self.filter.source.pts_time[index.row()]
            return new_pts - old_pts

    def fgdata(self, index, obj):
        diff = self.editdata(index, obj)

        if diff is not None:
            if abs(diff) >= 2/QQ(24000/1001):
                return self.white

            elif abs(diff) >= 1/QQ(24000/1001):
                return self.red

            elif abs(diff) < 0.2/QQ(24000/1001):
                return self.blue

            return self.fgcolor

    def bgdata(self, index, obj):
        diff = self.editdata(index, obj)

        if diff is not None and abs(diff) >= 2/QQ(24000/1001):
            return self.red

        return self.bgcolor
