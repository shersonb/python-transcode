import matroska.tags
import transcode.util
from collections import OrderedDict, UserList
import os

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
        self.subtags = list(subtags)

    def prepare(self, level=0, logfile=None):
        if self.string and self.binary:
            data = f"{self.string} (<data>)"

        elif self.string:
            data = self.string

        else:
            data = "<data>"

        langstr = f"-{self.language}" if self.language else ""

        print(f"    {' '*4*level}{self.name}{langstr}: {data}", file=logfile)
        subtags = [subtag.prepare(level + 1, logfile=logfile) for subtag in self.subtags]

        return matroska.tags.SimpleTag(self.name, self.language, self.languageIETF, self.default,
                                      self.string, self.binary, subtags)

    def __reduce__(self):
        return self.__class__, (self.name,), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()

        if self.language:
            state["language"] = self.language

        if self.mimeType:
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

class BaseTag(object):
    from copy import deepcopy as copy
    type = None
    typeValue = None
    simpletags = []

    def __init__(self, tracks=[], editions=[], chapters=[], attachments=[]):
        self.tracks = list(tracks)
        self.editions = list(editions)
        self.chapters = list(chapters)
        self.attachments = list(attachments)

    def __reduce__(self):
        return self.__class__, (), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()

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
        self.tracks = state.get("tracks", [])
        self.editions = state.get("editions", [])
        self.chapters = state.get("chapters", [])
        self.attachments = state.get("attachments", [])

    def prepare(self, logfile=None):
        print(f"{self.type} ({self.typeValue}):", file=logfile)

        if len(self.tracks):
            print(f"    Tracks: {', '.join(str(item) for item in self.tracks)}:", file=logfile)

        if len(self.editions):
            print(f"    Editions: {', '.join(str(item) for item in self.editions)}:", file=logfile)

        if len(self.tracks):
            print(f"    Chapters: {', '.join(str(item) for item in self.chapters)}:", file=logfile)

        if len(self.tracks):
            print(f"    Attachments: {', '.join(str(item) for item in self.attachments)}:", file=logfile)

        targets = matroska.tags.Targets(self.typeValue, self.type,
                                        self.tracks, self.editions, self.chapters, self.attachments)
        simpletags = [simpletag.prepare(0, logfile) for simpletag in self.simpletags]

        return matroska.tags.Tag(targets, simpletags)

class Tag(BaseTag):
    def __init__(self, typeValue=None, type=None, simpletags=[],
                 tracks=[], editions=[], chapters=[], attachments=[]):
        self.typeValue = typeValue
        self.type = type
        self.simpletags = list(simpletags)
        super().__init__(tracks, editions, chapters, attachments)

    def __getstate__(self):
        state = OrderedDict()

        if self.typeValue is not None:
            state["typeValue"] = self.typeValue

        if self.type is not None:
            state["type"] = self.type

        if self.tags is not None:
            state["simpletags"] = self.simpletags

        state.update(super().__getstate__())

        return state

    def __setstate__(self, state):
        self.typeValue = state.get("typeValue")
        self.type = state.get("type")
        self.simpletags = state.get("simpletags")
        super().__setstate__(state)

class TVSeriesTag(BaseTag):
    typeValue = 70
    type = "COLLECTION"

    def __init__(self, title=None, nSeasons=None, tracks=[], editions=[], chapters=[], attachments=[]):
        self.title = title
        self.nSeasons = nSeasons
        super().__init__(tracks, editions, chapters, attachments)

    @property
    def simpletags(self):
        simpletags = []

        if isinstance(self.title, dict):
            for lang, title in self.title.items():
                simpletags.append(SimpleTag("TITLE", lang, string=title))

        elif isinstance(self.title, str):
            simpletags.append(SimpleTag("TITLE", string=self.title))

        if isinstance(self.nSeasons, int):
            simpletags.append(SimpleTag("TOTAL_PARTS", string=self.nSeasons))

        return simpletags

    def __getstate__(self):
        state = OrderedDict()

        if self.title is not None:
            state["title"] = self.title

        if self.type is not None:
            state["nSeasons"] = self.nSeasons

        state.update(super().__getstate__())
        return state

    def __setstate__(self, state):
        self.title = state.get("title")
        self.nSeasons = state.get("nSeasons")
        super().__setstate__(state)

class TVSeasonTag(BaseTag):
    typeValue = 60
    type = "SEASON"

    def __init__(self, part=None, released=None, nEpisodes=None, tracks=[], editions=[], chapters=[], attachments=[]):
        self.part = part
        self.released = released
        self.nEpisodes = nEpisodes
        super().__init__(tracks, editions, chapters, attachments)

    @property
    def simpletags(self):
        simpletags = []

        if isinstance(self.part, (int, str)):
            simpletags.append(SimpleTag("PART_NUMBER", string=self.part))

        if isinstance(self.released, (int, str)):
            simpletags.append(SimpleTag("DATE_RELEASED", string=self.released))

        if isinstance(self.nEpisodes, (int, str)):
            simpletags.append(SimpleTag("TOTAL_PARTS", string=self.nEpisodes))

        return simpletags

    def __getstate__(self):
        state = OrderedDict()

        if self.part is not None:
            state["part"] = self.part

        if self.released is not None:
            state["released"] = self.released

        if self.nEpisodes is not None:
            state["nEpisodes"] = self.nEpisodes

        state.update(super().__getstate__())
        return state

    def __setstate__(self, state):
        self.part = state.get("part")
        self.released = state.get("released")
        self.nEpisodes = state.get("nEpisodes")
        super().__setstate__(state)

class TVEpisodeTag(BaseTag):
    typeValue = 50
    type = "EPISODE"

    def __init__(self, title=None, part=None, tracks=[], editions=[], chapters=[], attachments=[]):
        self.title = title
        self.part = part
        super().__init__(tracks, editions, chapters, attachments)

    @property
    def simpletags(self):
        simpletags = []

        if isinstance(self.title, dict):
            for lang, title in self.title.items():
                simpletags.append(SimpleTag("TITLE", lang, string=title))

        elif isinstance(self.title, str):
            simpletags.append(SimpleTag("TITLE", string=self.title))

        if isinstance(self.part, (int, str)):
            simpletags.append(SimpleTag("PART_NUMBER", string=self.part))

        return simpletags

    def __getstate__(self):
        state = OrderedDict()

        if self.title is not None:
            state["title"] = self.title

        if self.part is not None:
            state["part"] = self.part

        state.update(super().__getstate__())
        return state

    def __setstate__(self, state):
        self.title = state.get("title")
        self.part = state.get("part")
        super().__setstate__(state)

class MovieTag(BaseTag):
    typeValue = 50
    type = "MOVIE"

    def __init__(self, title=None, director=None, date_released=None, comment=None, tracks=[], editions=[], chapters=[], attachments=[]):
        self.title = title
        self.director = director
        self.date_released = date_released
        self.comment = comment
        super().__init__(tracks, editions, chapters, attachments)

    @property
    def simpletags(self):
        simpletags = []

        if isinstance(self.title, dict):
            for lang, title in self.title.items():
                simpletags.append(SimpleTag("TITLE", lang, string=title))

        elif isinstance(self.title, str):
            simpletags.append(SimpleTag("TITLE", string=self.title))

        if isinstance(self.director, str):
            simpletags.append(SimpleTag("DIRECTOR", string=self.director))

        if isinstance(self.date_released, (str, int)):
            simpletags.append(SimpleTag("DATE_RELEASED", string=self.date_released))

        if isinstance(self.comment, dict):
            for lang, comment in self.comment.items():
                simpletags.append(SimpleTag("COMMENT", lang, string=comment))

        elif isinstance(self.comment, str):
            simpletags.append(SimpleTag("COMMENT", string=self.comment))

        return simpletags

    def __getstate__(self):
        state = OrderedDict()

        if self.title is not None:
            state["title"] = self.title

        if self.director is not None:
            state["director"] = self.director

        if self.date_released is not None:
            state["date_released"] = self.date_released

        if self.comment is not None:
            state["comment"] = self.comment

        state.update(super().__getstate__())
        return state

    def __setstate__(self, state):
        self.title = state.get("title")
        self.director = state.get("director")
        self.date_released = state.get("date_released")
        self.comment = state.get("comment")
        super().__setstate__(state)


class Tags(transcode.util.ChildList):
    def prepare(self, logfile=None):
        print("--- Tags ---", file=logfile)
        return matroska.tags.Tags([attachment.prepare(logfile) for attachment in self])
