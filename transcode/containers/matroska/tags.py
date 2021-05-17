import matroska.tags
from transcode.util import ChildList, cached, WeakRefList
from collections import OrderedDict, UserList
import os
from xml.dom.minidom import Document, Element, Text, DocumentType
import base64
import regex
from .uid import formatUID


class SimpleTag(object):
    from copy import deepcopy as copy

    def __init__(self, name, language=None, languageIETF=None, default=None,
                 string=None, binary=None, subtags=[], parent=None):
        self.name = name
        self.language = language
        self.languageIETF = languageIETF
        self.default = default
        self.string = string
        self.binary = binary
        self.subtags = subtags
        self.parent = parent

    def toXml(self):
        xml = Element("Simple")

        child = Element("Name")
        text = Text()
        text.data = self.name
        child.appendChild(text)
        xml.appendChild(child)

        if self.string is not None:
            child = Element("String")
            text = Text()
            text.data = self.string
            child.appendChild(text)
            xml.appendChild(child)

        if self.binary is not None:
            child = Element("Binary")
            text = Text()
            text.data = base64.encodebytes(self.binary).decode("utf8")
            child.appendChild(text)
            xml.appendChild(child)

        if self.language is not None:
            child = Element("TagLanguage")
            text = Text()
            text.data = self.language
            child.appendChild(text)
            xml.appendChild(child)

        if self.default:
            child = Element("DefaultLanguage")
            text = Text()
            text.data = "1"
            child.appendChild(text)
            xml.appendChild(child)

        for subtag in self.subtags:
            xml.appendChild(subtag.toXml())

        return xml

    @classmethod
    def fromXml(cls, xml):
        name = None
        language = None
        languageIETF = None
        default = None
        string = None
        binary = None
        subtags = []

        if xml.tagName != "Simple":
            raise ValueError(
                f"Expected Simple element. Got {xml.tagName} instead.")

        for node in xml.childNodes:
            if isinstance(node, Text):
                if not regex.match(r"^\s*$", node.data, flags=regex.M):
                    raise ValueError(f"Unexpected Data: {n}")

            if isinstance(node, Element):
                if node.tagName == "Name":
                    name = ""

                    for subnode in node.childNodes:
                        if isinstance(subnode, Element):
                            raise ValueError(
                                f"Unexpected subtag of Name found ({subnode.tagName}).")

                        elif isinstance(subnode, Text):
                            name += subnode.data

                elif node.tagName == "TagLanguage":
                    language = ""

                    for subnode in node.childNodes:
                        if isinstance(subnode, Element):
                            raise ValueError(
                                f"Unexpected subtag of Language found ({subnode.tagName}).")

                        elif isinstance(subnode, Text):
                            language += subnode.data

                elif node.tagName == "DefaultLanguage":
                    default = True

                elif node.tagName == "String":
                    string = ""

                    for subnode in node.childNodes:
                        if isinstance(subnode, Element):
                            raise ValueError(
                                f"Unexpected subtag of String found ({subnode.tagName}).")

                        elif isinstance(subnode, Text):
                            string += subnode.data

                elif node.tagName == "Binary":
                    binary = b""

                    for subnode in node.childNodes:
                        if isinstance(subnode, Element):
                            raise ValueError(
                                f"Unexpected subtag of Language found ({subnode.tagName}).")

                        elif isinstance(subnode, Text):
                            binary += base64.decodebytes(
                                subnode.data.encode('utf8'))

                elif node.tagName == "Simple":
                    subtags.append(SimpleTag.fromXml(node))

                else:
                    raise ValueError(
                        f"Unexpected subtag of Tag found ({subnode.tagName}).")

        return cls(name, language, languageIETF, default,
                   string, binary, subtags)

    @property
    def subtags(self):
        return self._subtags

    @subtags.setter
    def subtags(self, value):
        self._subtags = ChildList(value, self)

    def prepare(self, level=0, logfile=None):
        if self.string and self.binary:
            data = f"{self.string} (<data>)"

        elif self.string:
            data = self.string

        else:
            data = "<data>"

        langstr = f"-{self.language}" if self.language else ""

        print(f"    {' '*4*level}{self.name}{langstr}: {data}", file=logfile)
        subtags = [subtag.prepare(level + 1, logfile=logfile)
                   for subtag in self.subtags]

        return matroska.tags.SimpleTag(self.name, self.language, self.languageIETF, self.default,
                                       self.string, self.binary, subtags)

    def __reduce__(self):
        return self.__class__, (self.name,), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()

        if self.language:
            state["language"] = self.language

        if self.languageIETF:
            state["languageIETF"] = self.languageIETF

        if self.default:
            state["default"] = self.default

        if self.string:
            state["string"] = self.string

        if self.binary:
            state["binary"] = self.binary

        if self.subtags:
            state["subtags"] = self.subtags

        return state

    def __setstate__(self, state):
        self.language = state.get("language")
        self.languageIETF = state.get("languageIETF")
        self.default = state.get("default")
        self.string = state.get("string")
        self.binary = state.get("binary")
        self.subtags = state.get("subtags", [])


class Tag(object):
    from copy import deepcopy as copy

    def __init__(self, typeValue=None, type=None, simpletags=[],
                 tracks=[], editions=[], chapters=[], attachments=[]):
        if typeValue is not None:
            self.typeValue = int(typeValue)

        self.type = type
        self.simpletags = simpletags
        self.tracks = WeakRefList(tracks)
        self.editions = WeakRefList(editions)
        self.chapters = WeakRefList(chapters)
        self.attachments = WeakRefList(attachments)

    @property
    def simpletags(self):
        return self._simpletags

    @simpletags.setter
    def simpletags(self, value):
        self._simpletags = ChildList(value, self)

    def __reduce__(self):
        return self.__class__, (), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()

        if self.typeValue is not None:
            state["typeValue"] = self.typeValue

        if self.type is not None:
            state["type"] = self.type

        if self.simpletags is not None:
            state["simpletags"] = self.simpletags

        self.tracks.clean()
        self.editions.clean()
        self.chapters.clean()
        self.attachments.clean()

        if self.tracks:
            state["tracks"] = self.tracks

        if self.editions:
            state["editions"] = self.editions

        if self.chapters:
            state["chapters"] = self.chapters

        if self.attachments:
            state["attachments"] = self.attachments

        return state

    def __setstate__(self, state):
        try:
            self.typeValue = int(state.get("typeValue"))

        except ValueError:
            pass

        self.type = state.get("type")
        self.simpletags = state.get("simpletags")
        self.tracks = WeakRefList(state.get("tracks", []))
        self.editions = WeakRefList(state.get("editions", []))
        self.chapters = WeakRefList(state.get("chapters", []))
        self.attachments = WeakRefList(state.get("attachments", []))

    def prepare(self, logfile=None):
        print(f"{self.type} ({self.typeValue}):", file=logfile)

        self.tracks.clean()
        self.editions.clean()
        self.chapters.clean()
        self.attachments.clean()

        if len(self.tracks):
            print(
                f"    Target Tracks: {', '.join(formatUID(item.trackUID) for item in self.tracks)}", file=logfile)

        if len(self.editions):
            print(
                f"    Target Editions: {', '.join(formatUID(item.UID) for item in self.editions)}", file=logfile)

        if len(self.chapters):
            print(
                f"    Target Chapters: {', '.join(formatUID(item.UID) for item in self.chapters)}", file=logfile)

        if len(self.attachments):
            print(
                f"    Target Attachments: {', '.join(formatUID(item.UID) for item in self.attachments)}", file=logfile)


        targets = matroska.tags.Targets(self.typeValue, self.type,
                                        [item.trackUID for item in self.tracks],
                                        [item.UID for item in self.editions],
                                        [item.UID for item in self.chapters],
                                        [item.UID for item in self.attachments])
        simpletags = [simpletag.prepare(0, logfile)
                      for simpletag in self.simpletags]

        return matroska.tags.Tag(targets, simpletags)

    def toXml(self):
        xml = Element("Tag")

        targets = Element("Targets")

        targetschild = Element("TargetTypeValue")
        text = Text()
        text.data = str(self.typeValue)
        targetschild.appendChild(text)
        targets.appendChild(targetschild)

        targetschild = Element("TargetType")
        text = Text()
        text.data = self.type
        targetschild.appendChild(text)
        targets.appendChild(targetschild)

        xml.appendChild(targets)

        for item in self.tracks:
            child = Element("TrackUID")
            text = Text()
            text.data = str(item.trackUID)
            child.appendChild(text)
            targets.appendChild(child)

        for item in self.chapters:
            child = Element("ChapterUID")
            text = Text()
            text.data = str(item.UID)
            child.appendChild(text)
            targets.appendChild(child)

        for item in self.attachments:
            child = Element("AttachmentUID")
            text = Text()
            text.data = str(item.UID)
            child.appendChild(text)
            targets.appendChild(child)

        for item in self.editions:
            child = Element("EditionUID")
            text = Text()
            text.data = str(item.UID)
            child.appendChild(text)
            targets.appendChild(child)

        for subtag in self.simpletags:
            xml.appendChild(subtag.toXml())

        return xml

    @classmethod
    def fromXml(cls, xml):
        typeValue = None
        type = None
        simpletags = []
        tracks = []
        editions = []
        chapters = []
        attachments = []

        if xml.tagName != "Tag":
            raise ValueError(
                f"Expected Tag element. Got {xml.tagName} instead.")

        for node in xml.childNodes:
            if isinstance(node, Text):
                if not regex.match(r"^\s*$", node.data, flags=regex.M):
                    raise ValueError(f"Unexpected Data: {n}")

            if isinstance(node, Element):
                if node.tagName == "Targets":
                    for subnode in node.childNodes:
                        if isinstance(subnode, Text):
                            if not regex.match(r"^\s*$", subnode.data, flags=regex.M):
                                raise ValueError(f"Unexpected Data: {n}")

                        elif isinstance(subnode, Element):
                            if subnode.tagName == "TargetTypeValue":
                                typeValue = ""

                                for subsubnode in subnode.childNodes:
                                    if isinstance(subsubnode, Element):
                                        raise ValueError(
                                            f"Unexpected subtag of TargetTypeValue found ({subsubnode.tagName}).")

                                    elif isinstance(subsubnode, Text):
                                        typeValue += subsubnode.data

                            elif subnode.tagName == "TargetType":
                                type = ""

                                for subsubnode in subnode.childNodes:
                                    if isinstance(subsubnode, Element):
                                        raise ValueError(
                                            f"Unexpected subtag of TargetType found ({subsubnode.tagName}).")

                                    elif isinstance(subsubnode, Text):
                                        type += subsubnode.data

                            elif subnode.tagName == "TrackUID":
                                for subsubnode in subnode.childNodes:
                                    if isinstance(subsubnode, Element):
                                        raise ValueError(
                                            f"Unexpected subtag of TrackUID found ({subsubnode.tagName}).")

                                    elif isinstance(subsubnode, Text):
                                        if not regex.match(r"^\d+$", subsubnode.data.strip()):
                                            print(subsubnode.data.strip())
                                            raise ValueError(
                                                f"Non-integer data found in TrackUID tag.")

                                        tracks.append(
                                            int(subsubnode.data.strip()))

                            elif subnode.tagName == "ChapterUID":
                                for subsubnode in subnode.childNodes:
                                    if isinstance(subsubnode, Element):
                                        raise ValueError(
                                            f"Unexpected subtag of ChapterUID found ({subsubnode.tagName}).")

                                    elif isinstance(subsubnode, Text):
                                        if not regex.match(r"^\d+$", subsubnode.data.strip()):
                                            raise ValueError(
                                                f"Non-integer data found in ChapterUID tag.")

                                        chapters.append(
                                            int(subsubnode.data.strip()))

                            elif subnode.tagName == "AttachmentUID":
                                for subsubnode in subnode.childNodes:
                                    if isinstance(subsubnode, Element):
                                        raise ValueError(
                                            f"Unexpected subtag of AttachmentUID found ({subsubnode.tagName}).")

                                    elif isinstance(subsubnode, Text):
                                        if not regex.match(r"^\d+$", subsubnode.data.strip()):
                                            raise ValueError(
                                                f"Non-integer data found in AttachmentUID tag.")

                                        attachments.append(
                                            int(subsubnode.data.strip()))

                            elif subnode.tagName == "EditionUID":
                                for subsubnode in subnode.childNodes:
                                    if isinstance(subsubnode, Element):
                                        raise ValueError(
                                            f"Unexpected subtag of EditionUID found ({subsubnode.tagName}).")

                                    elif isinstance(subsubnode, Text):
                                        if not regex.match(r"^\d+$", subsubnode.data.strip()):
                                            raise ValueError(
                                                f"Non-integer data found in EditionUID tag.")

                                        editions.append(
                                            int(subsubnode.data.strip()))

                elif node.tagName == "Simple":
                    simpletags.append(SimpleTag.fromXml(node))

                else:
                    raise ValueError(
                        f"Unexpected subtag of Tag found ({node.tagName}).")

        return cls(typeValue, type, simpletags,
                   tracks, editions, chapters, attachments)


class Tags(ChildList):
    def prepare(self, logfile=None):
        print("--- Tags ---", file=logfile)
        return matroska.tags.Tags([attachment.prepare(logfile) for attachment in self])

    def toXml(self, selected=None):
        doc = Document()
        doctype = DocumentType("Tags")
        doctype.systemId = "matroskatags.dtd"
        tags = Element("Tags")

        for item in (selected or self):
            tags.appendChild(item.toXml())

        doc.appendChild(doctype)
        doc.appendChild(tags)

        return doc

    @classmethod
    def fromXml(cls, xml):
        if xml.documentElement.tagName != "Tags":
            raise ValueError(
                f"Expected Tags element as Document Element. Got {xml.documentElement.tagName} instead.")

        tags = []

        for node in xml.documentElement.childNodes:
            if isinstance(node, Text):
                if not regex.match(r"^\s*$", node.data, flags=regex.M):
                    raise ValueError(f"Unexpected Data: {n}")

            if isinstance(node, Element):
                tags.append(Tag.fromXml(node))

        return cls(tags)
