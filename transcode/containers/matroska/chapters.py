import matroska.chapters
from transcode.util import ChildList, llist
from collections import OrderedDict, UserList
from .uid import formatUID
from xml.dom.minidom import Document, Element, Text, DocumentType
import regex


def str2pts(data):
    (h, m, s, ns), = regex.findall(r"^(?:(\d+):)?(\d+):(\d+)(?:\.(\d+))?$", data)

    if ns is not None:
        ns = int(ns)*10**(9-len(ns))

    else:
        ns = 0

    s = int(s)
    m = int(m)

    if h is not None:
        h = int(h)

    else:
        h = 0

    return ((h*60 + m)*60 + s)*10**9 + ns


class ChapterDisplay(object):
    from copy import deepcopy as copy

    def __init__(self, string, languages=["eng"], langIETF=[], countries=["us"], parent=None):
        self.string = string
        self.languages = languages.copy()
        self.langIETF = langIETF.copy()
        self.countries = countries.copy()
        self.parent = parent

    def prepare(self, logfile=None):
        print(f"        Name: {self.string}", file=logfile)
        print(
            f"            Lanugages: {', '.join(self.languages)}", file=logfile)
        print(
            f"            Countries: {', '.join(self.countries)}", file=logfile)
        return matroska.chapters.ChapterDisplay(self.string, self.languages,
                                                self.langIETF, self.countries)

    def __reduce__(self):
        return self.__class__, (self.string,), self.__getstate__()

    def __getstate__(self):
        state = {}
        state["languages"] = self.languages
        state["langIETF"] = self.langIETF
        state["countries"] = self.countries
        return state

    def __setstate__(self, state):
        self.languages = state.get("languages", ["eng"])
        self.langIETF = state.get("langIETF", [])
        self.countries = state.get("countries", ["us"])

    def _handleStringNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of ChapterString found ({subsubnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

        self.string = data

    def _handleLangNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of ChapterLanguage found ({subsubnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

        self.languages.append(data)

    def _handleLangIETFNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of ChapterLanguageIETF found ({subsubnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

        self.langIETF.append(data)

    def _handleCountryNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of ChapterCountry found ({subsubnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

        self.countries.append(data)

    def toXml(self):
        xml = Element("ChapterDisplay")

        subtag = Element("ChapterString")
        text = Text()
        text.data = self.string
        subtag.appendChild(text)
        xml.appendChild(subtag)

        for lang in self.languages:
            subtag = Element("ChapterLanguage")
            text = Text()
            text.data = lang
            subtag.appendChild(text)
            xml.appendChild(subtag)

        for lang in self.langIETF:
            subtag = Element("ChapterLanguageIETF")
            text = Text()
            text.data = lang
            subtag.appendChild(text)
            xml.appendChild(subtag)

        for country in self.countries:
            subtag = Element("ChapterCountry")
            text = Text()
            text.data = country
            subtag.appendChild(text)
            xml.appendChild(subtag)

        return xml

    @classmethod
    def fromXml(cls, xml, parent=None):
        expected = "ChapterDisplay"

        if xml.tagName != expected:
            raise ValueError(
                f"Expected {expected} element. Got {xml.tagName} instead.")

        self = cls(0, [], [], [], parent=parent)

        for node in xml.childNodes:
            if isinstance(node, Text):
                if not regex.match(r"^\s*$", node.data, flags=regex.M):
                    raise ValueError(f"Unexpected Data: {n}")

            if isinstance(node, Element):
                if node.tagName == "ChapterString":
                    self._handleStringNode(node)

                elif node.tagName == "ChapterLanguage":
                    self._handleLangNode(node)

                elif node.tagName == "ChapterLanguageIETF":
                    self._handleLangIETFNode(node)

                elif node.tagName == "ChapterCountry":
                    self._handleCountryNode(node)

                else:
                    raise ValueError(
                        f"Unexpected subtag of {expected} found ({node.tagName}).")

        return self


class ChapterAtom(object):
    from copy import deepcopy as copy

    def __init__(self, UID, startFrame=None, endFrame=None, timeStart=None, timeEnd=None, displays=[], hidden=False, enabled=True, segmentUID=None,
                 segmentEditionUID=None, physicalEquiv=None, tracks=None, next=None, prev=None, parent=None):
        self.UID = UID
        self.startFrame = startFrame
        self.endFrame = endFrame
        self._timeStart = timeStart
        self._timeEnd = timeEnd
        self.displays = displays.copy()
        self.hidden = hidden
        self.enabled = enabled
        self.segmentUID = segmentUID
        self.segmentEditionUID = segmentEditionUID
        self.physicalEquiv = physicalEquiv
        self.tracks = tracks
        self.next = next
        self.prev = prev
        self.parent = parent

    @property
    def displays(self):
        return self._displays

    @displays.setter
    def displays(self, value):
        self._displays = ChildList(value, self)

    @property
    def mkvfile(self):
        if isinstance(self.parent, EditionEntry):
            return self.parent.parent

    @property
    def config(self):
        if self.mkvfile:
            return self.mkvfile.config

    @property
    def segment(self):
        if self.segmentUID and self.config:
            for outputfile in self.config.output_files:
                if outputfile.segmentUID == self.segmentUID:
                    return outputfile

            return

        return self.mkvfile

    @property
    def timeStart(self):
        if self.startFrame is not None and self.segment:
            return self._mapSrcFrameToPts(self.startFrame)

        return self._timeStart

    @timeStart.setter
    def timeStart(self, value):
        self._timeStart = value

        if value is not None:
            self.startFrame = None

    @property
    def timeEnd(self):
        if self.parent:
            if self.parent.ordered and self.segment:
                if self.endFrame is None:
                    return

                return self._mapSrcFrameToPts(self.endFrame)

            elif self.next:
                return self.next.timeStart

            elif self.segment and self.segment.vtrack:
                return int(self.segment.vtrack.duration/self.segment.vtrack.time_base)

        return self._timeEnd

    @timeEnd.setter
    def timeEnd(self, value):
        self._timeEnd = value

        if value is not None:
            self.endFrame = None

    @property
    def startFrame(self):
        return self._startFrame

    @startFrame.setter
    def startFrame(self, value):
        self._startFrame = value

        if value is not None:
            self._timeStart = None

    @property
    def endFrame(self):
        return self._endFrame

    @endFrame.setter
    def endFrame(self, value):
        self._endFrame = value

        if value is not None:
            self._timeEnd = None

    def prepare(self, logfile=None):
        flagstrings = [f"UID {formatUID(self.UID)}"]

        if self.enabled:
            flagstrings.append("Enabled")

        if self.hidden:
            flagstrings.append("Hidden")

        m, ms = divmod(self.timeStart, 60*10**9)
        s1 = ms/10**9
        h1, m1 = divmod(m, 60)

        print(
            f"    Chapter {self.parent.index(self) + 1}: {', '.join(flagstrings)}", file=logfile)

        ebml = matroska.chapters.ChapterAtom(
            chapterUID=self.UID,
            chapterTimeStart=self.timeStart,
            chapterTimeEnd=self.timeEnd,
            chapterFlagHidden=self.hidden,
            chapterFlagEnabled=self.enabled,
            chapterSegmentUID=self.segmentUID, 
            chapterSegmentEditionUID=self.segmentEditionUID,
            chapterTrack=self.tracks,
            chapterDisplays=[
                display.prepare(logfile)
                for display in self.displays])

        if self.timeEnd:
            m, ms = divmod(self.timeEnd, 60*10**9)
            s2 = ms/10**9
            h2, m2 = divmod(m, 60)
            print(
                f"        Time: {h1}:{m1:02d}:{s1:06.3f} — {h2}:{m2:02d}:{s2:06.3f}", file=logfile)

        else:
            print(
                f"        Time: {h1}:{m1:02d}:{s1:06.3f} — ?:??:??.???", file=logfile)

        return ebml

    def __reduce__(self):
        return self.__class__, (self.UID,), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()

        if self.startFrame is not None:
            state["startFrame"] = self.startFrame

        if self.endFrame is not None and self.parent and self.parent.ordered:
            state["endFrame"] = self.endFrame

        if self._timeStart is not None:
            state["timeStart"] = self._timeStart

        if self._timeEnd is not None:
            state["timeEnd"] = self._timeEnd

        if self.displays is not None:
            state["displays"] = self.displays

        if self.hidden is not None:
            state["hidden"] = self.hidden

        if self.enabled is not None:
            state["enabled"] = self.enabled

        if self.segmentUID is not None:
            state["segmentUID"] = self.segmentUID

        if self.segmentEditionUID is not None:
            state["segmentEditionUID"] = self.segmentEditionUID

        if self.physicalEquiv is not None:
            state["physicalEquiv"] = self.physicalEquiv

        if self.tracks is not None:
            state["tracks"] = self.tracks

        return state

    def __setstate__(self, state):
        if "startFrame" in state:
            self.startFrame = state.get("startFrame")

        self.endFrame = state.get("endFrame")

        self._timeStart = state.get("timeStart")
        self._timeEnd = state.get("timeEnd")

        self.displays = state.get("displays", [])
        self.hidden = state.get("hidden", False)
        self.enabled = state.get("enabled", True)
        self.segmentUID = state.get("segmentUID")
        self.segmentEditionUID = state.get("segmentEditionUID")
        self.physicalEquiv = state.get("physicalEquiv")
        self.tracks = state.get("tracks")

    def toXml(self):
        xml = Element("ChapterAtom")

        subtag = Element("ChapterUID")
        text = Text()
        text.data = str(self.UID)
        subtag.appendChild(text)
        xml.appendChild(subtag)

        if self.timeStart is not None:
            subtag = Element("ChapterTimeStart")
            text = Text()

            m, ms = divmod(self.timeStart, 60*10**9)
            s1 = ms/10**9
            h1, m1 = divmod(m, 60)

            text.data = f"{h1}:{m1:02d}:{s1:012.9f}"
            subtag.appendChild(text)
            xml.appendChild(subtag)

        if self.timeEnd is not None:
            subtag = Element("ChapterTimeEnd")
            text = Text()

            m, ms = divmod(self.timeEnd, 60*10**9)
            s1 = ms/10**9
            h1, m1 = divmod(m, 60)

            text.data = f"{h1}:{m1:02d}:{s1:012.9f}"
            subtag.appendChild(text)
            xml.appendChild(subtag)

        subtag = Element("ChapterFlagHidden")
        text = Text()
        text.data = str(int(bool(self.hidden)))
        subtag.appendChild(text)
        xml.appendChild(subtag)

        subtag = Element("ChapterFlagEnabled")
        text = Text()
        text.data = str(int(bool(self.enabled)))
        subtag.appendChild(text)
        xml.appendChild(subtag)

        # TODO

        if self.segmentUID is not None:
            pass

        if self.segmentEditionUID is not None:
            pass

        if self.tracks is not None:
            pass

        for display in self.displays:
            xml.appendChild(display.toXml())

        return xml

    def _handleUIDNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of ChapterString found ({subnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

            else:
                raise ValueError(
                    f"Unhandled subnode type ({subnode}).")

        self.UID = int(data)

    def _handleStartNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of ChapterTimeStart found ({subnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

            else:
                raise ValueError(
                    f"Unhandled subnode type ({subnode}).")

        pts = str2pts(data)
        n = self._mapPtsToSrcFrame(pts)

        if n is not None:
            self.startFrame = n

        else:
            self.timeStart = pts

    def _handleEndNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of ChapterTimeStart found ({subnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

            else:
                raise ValueError(
                    f"Unhandled subnode type ({subnode}).")

        pts = str2pts(data)
        n = self._mapPtsToSrcFrame(pts)

        if n is not None:
            self.endFrame = n

        else:
            self.timeEnd = pts

    def _mapPtsToSrcFrame(self, pts):
        if (self.segment is not None
                and self.segment.vtrack is not None
                and self.segment.vtrack.pts is not None):
            if pts > self.segment.vtrack.pts[-1]:
                return self.segment.vtrack.framecount

            else:
                n = self.segment.vtrack.frameIndexFromPts(pts)

                if self.segment.vtrack.filters:
                    n = self.segment.vtrack.filters.reverseIndexMap[n]

                return n

    def _mapSrcFrameToPts(self, n):
        if self.segment is not None:
            vtrack = self.segment.vtrack

            if vtrack is None:
                for vtrack in self.segment.tracks:
                    if vtrack.type == "video":
                        break

                else:
                    return

            if vtrack.filters is not None:
                k = -1

                while k < 0:
                    if n >= len(vtrack.filters.indexMap):
                        return int(vtrack.filters.duration/vtrack.filters.time_base)

                    k = vtrack.filters.indexMap[n]
                    n += 1

            else:
                k = self.startFrame

            return vtrack.pts[k]

    def _handleHiddenNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of ChapterFlagHidden found ({subsubnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

        self.hidden = int(data.strip())

    def _handleEnabledNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of ChapterFlagEnabled found ({subsubnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

        self.enabled = int(data.strip())


    def _handleDisplayNode(self, node):
        self.displays.append(ChapterDisplay.fromXml(node))

    @classmethod
    def fromXml(cls, xml, parent=None):
        expected = "ChapterAtom"

        if xml.tagName != expected:
            raise ValueError(
                f"Expected {expected} element. Got {xml.tagName} instead.")

        self = cls(0, parent=parent)

        for node in xml.childNodes:
            if isinstance(node, Text):
                if not regex.match(r"^\s*$", node.data, flags=regex.M):
                    raise ValueError(f"Unexpected Data: {n}")

            if isinstance(node, Element):
                if node.tagName == "ChapterUID":
                    self._handleUIDNode(node)

                elif node.tagName == "ChapterTimeStart":
                    self._handleStartNode(node)

                elif node.tagName == "ChapterTimeEnd":
                    self._handleEndNode(node)

                elif node.tagName == "ChapterFlagHidden":
                    self._handleHiddenNode(node)

                elif node.tagName == "ChapterFlagEnabled":
                    self._handleEnabledNode(node)

                elif node.tagName == "ChapterDisplay":
                    self._handleDisplayNode(node)

                else:
                    raise ValueError(
                        f"Unexpected subtag of {expected} found ({node.tagName}).")

        return self


class EditionEntry(llist):
    def __init__(self, chapters=[], UID=None, hidden=False, default=False, ordered=False, parent=None):
        self.UID = UID
        self.hidden = hidden
        self.default = default
        self.ordered = ordered
        self.parent = parent
        super().__init__(chapters)

    def insert(self, index, chapter):
        super().insert(index, chapter)

    def __getstate__(self):
        state = OrderedDict()
        state["UID"] = self.UID
        state["hidden"] = self.hidden
        state["default"] = self.default
        state["ordered"] = self.ordered
        return state

    def __setstate__(self, state):
        self.UID = state.get("UID")
        self.hidden = state.get("hidden", False)
        self.default = state.get("default", False)
        self.ordered = state.get("ordered", False)

    def prepare(self, logfile=None):
        flagstrings = []

        if self.default:
            flagstrings.append("Default")

        if self.hidden:
            flagstrings.append("Hidden")

        if self.ordered:
            flagstrings.append("Ordered")

        if len(flagstrings):
            print(
                f"Edition Entry {formatUID(self.UID)} ({', '.join(flagstrings)})", file=logfile)

        else:
            print(f"Edition Entry {formatUID(self.UID)}", file=logfile)

        return matroska.chapters.EditionEntry(
            editionUID=self.UID,
            editionFlagHidden=self.hidden,
            editionFlagDefault=self.default,
            chapterAtoms=[chapter.prepare(logfile) for chapter in self],
            editionFlagOrdered=self.ordered)

    def toXml(self):
        xml = Element("EditionEntry")

        subtag = Element("EditionUID")
        text = Text()
        text.data = str(self.UID)
        subtag.appendChild(text)
        xml.appendChild(subtag)

        subtag = Element("EditionFlagHidden")
        text = Text()
        text.data = str(int(bool(self.hidden)))
        subtag.appendChild(text)
        xml.appendChild(subtag)

        subtag = Element("EditionFlagDefault")
        text = Text()
        text.data = str(int(bool(self.default)))
        subtag.appendChild(text)
        xml.appendChild(subtag)

        subtag = Element("EditionFlagOrdered")
        text = Text()
        text.data = str(int(bool(self.ordered)))
        subtag.appendChild(text)
        xml.appendChild(subtag)

        for chapter in self:
            xml.appendChild(chapter.toXml())

        return xml

    def _handleUIDNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of EditionUID found ({subnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

            else:
                raise ValueError(
                    f"Unhandled subnode type ({subnode}).")

        self.UID = int(data)

    def _handleHiddenNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of EditionFlagHidden found ({subsubnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

        self.hidden = int(data.strip())

    def _handleDefaultNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of EditionFlagDefault found ({subsubnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

        self.default = int(data.strip())

    def _handleOrderedNode(self, node):
        data = ""

        for subnode in node.childNodes:
            if isinstance(subnode, Element):
                raise ValueError(
                    f"Unexpected subtag of EditionFlagOrdered found ({subsubnode.tagName}).")

            elif isinstance(subnode, Text):
                data += subnode.data

        self.ordered = int(data.strip())

    def _handleAtomNode(self, node):
        atom = ChapterAtom.fromXml(node, self)
        self.append(atom)

    @classmethod
    def fromXml(cls, xml, parent=None):
        expected = "EditionEntry"

        if xml.tagName != expected:
            raise ValueError(
                f"Expected {expected} element. Got {xml.tagName} instead.")

        self = cls(parent=parent)

        for node in xml.childNodes:
            if isinstance(node, Text):
                if not regex.match(r"^\s*$", node.data, flags=regex.M):
                    raise ValueError(f"Unexpected Data: {n}")

            if isinstance(node, Element):
                if node.tagName == "EditionUID":
                    self._handleUIDNode(node)

                elif node.tagName == "EditionFlagHidden":
                    self._handleHiddenNode(node)

                elif node.tagName == "EditionFlagDefault":
                    self._handleDefaultNode(node)

                elif node.tagName == "EditionFlagOrdered":
                    self._handleOrderedNode(node)

                elif node.tagName == "ChapterAtom":
                    self._handleAtomNode(node)

                else:
                    raise ValueError(
                        f"Unexpected subtag of {expected} found ({node.tagName}).")

        return self


class Editions(ChildList):
    def prepare(self, logfile=None):
        print("--- Chapters ---", file=logfile)
        return matroska.chapters.Chapters([edition.prepare(logfile) for edition in self])

    def toXml(self, selected=None):
        doc = Document()
        doctype = DocumentType("Chapters")
        doctype.systemId = "matroskachapters.dtd"
        editions = Element("Chapters")

        for item in (selected or self):
            editions.appendChild(item.toXml())

        doc.appendChild(doctype)
        doc.appendChild(editions)

        return doc

    @classmethod
    def fromXml(cls, xml, parent=None):
        if xml.documentElement.tagName != "Chapters":
            raise ValueError(
                f"Expected Chapters element as Document Element. Got {xml.documentElement.tagName} instead.")

        self = cls(parent=parent)

        for node in xml.documentElement.childNodes:
            if isinstance(node, Text):
                if not regex.match(r"^\s*$", node.data, flags=regex.M):
                    raise ValueError(f"Unexpected Data: {n}")

            if isinstance(node, Element):
                self.append(EditionEntry.fromXml(node, parent))

        return self
