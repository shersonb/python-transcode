import matroska.attachments
import transcode.util
from collections import OrderedDict, UserList
import pathlib
import mimetypes
import os
from copy import deepcopy

class AttachmentRef(object):
    from copy import copy

    def __init__(self, source, UID):
        self.source = source
        self.UID = UID

    def __reduce__(self):
        return self.__class__, (self.source, self.UID)

    def __deepcopy__(self, memo):
        """
        We want to keep the original reference to self.source.
        """
        memo.update({
                id(self.source): self.source,
            })

        reduced = self.__reduce__()

        if len(reduced) == 2:
            cls, args = reduced
            state = items = dictitems = None

        elif len(reduced) == 3:
            cls, args, state = reduced
            items = dictitems = None

        if len(reduced) == 4:
            cls, args, state, items = reduced
            dictitems = None

        if len(reduced) == 5:
            cls, args, state, items, dictitems = reduced

        new = cls(*(deepcopy(arg, memo) for arg in args))

        if state is not None:
            new.__setstate__(deepcopy(state, memo))

        if items is not None:
            new.extend(deepcopy(item, memo) for item in items)

        if dictitems is not None:
            new.update(deepcopy(dictitems, memo))

        return new

    @property
    def attachment(self):
        if self.source.attachments:
            for attachment in self.source.attachments:
                if attachment.fileUID == self.UID:
                    return attachment

            else:
                raise KeyError(f"Attachment with fileUID {self.UID} not found.")

        raise KeyError(f"Attachment with fileUID {self.UID} not found.")

    @property
    def fileName(self):
        return self.attachment.fileName

    @property
    def mimeType(self):
        return self.attachment.mimeType

    @property
    def description(self):
        return self.attachment.description

class AttachedFile(object):
    from copy import deepcopy as copy

    def __init__(self, UID, source=None, fileName=None, mimeType=None, description=None, parent=None):
        self.UID = UID
        self.source = source
        self.fileName = fileName
        self.mimeType = mimeType
        self.description = description
        self.parent = parent

    @property
    def fileName(self):
        if self._fileName is not None:
            return self._fileName

        elif isinstance(self.source, AttachmentRef):
            return self.source.fileName

        elif isinstance(self.source, pathlib.Path):
            return self.source.name

    @fileName.setter
    def fileName(self, value):
        self._fileName = value

    @property
    def mimeType(self):
        if self._mimeType:
            return self._mimeType

        elif isinstance(self.source, AttachmentRef):
            return self.source.mimeType

        elif isinstance(self.source, pathlib.Path):
            mimeType, encoding = mimetypes.MimeTypes().guess_type(str(self.source))
            return mimeType

    @mimeType.setter
    def mimeType(self, value):
        self._mimeType = value

    @property
    def fileData(self):
        if isinstance(self.source, AttachmentRef):
            if isinstance(self.source.attachment.fileData, matroska.attachments.FilePointer):
                return b"".join(self.source.attachment.fileData)

            elif isinstance(self.source.attachment.fileData, bytes):
                return self.source.attachment.fileData

        elif isinstance(self.source, pathlib.Path):
            with open(self.source, "rb") as f:
                return f.read()

    def prepare(self, logfile=None):
        print(f"Attachment {self.UID}", file=logfile)
        print(f"    Filename: {self.fileName}", file=logfile)
        print(f"    Mimetype: {self.mimeType}", file=logfile)

        if isinstance(self.source, AttachmentRef):
            attachment = self.source.attachment.copy()
            attachment.fileName = self.fileName
            attachment.mimeType = self.mimeType
            attachment.description = self.description
            attachment.fileUID = self.UID
            return attachment

        elif isinstance(self.source, pathlib.Path):
            attachment = matroska.attachments.AttachedFile.fromPath(str(self.source), self.mimeType, self.UID, self.description)
            attachment.fileName = self.fileName
            return attachment

    def __reduce__(self):
        return self.__class__, (self.UID, self.source), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()

        if self._fileName:
            state["fileName"] = self._fileName

        if self._mimeType:
            state["mimeType"] = self._mimeType

        if self.description:
            state["description"] = self.description

        return state

    def __setstate__(self, state):
        self._fileName = state.get("fileName")
        self._mimeType = state.get("mimeType")
        self.description = state.get("description")

    @property
    def source(self):
        return self._source

    @source.setter
    def source(self, value):
        if isinstance(value, str):
            value = pathlib.Path(value)

        self._source = value

    @property
    def sourcerel(self):
        """Input file path relative to config path."""
        if isinstance(self.source, pathlib.Path) and self.parent and self.parent.config:
            relpath = os.path.relpath(self.source, self.parent.config.workingdir)

            if relpath.startswith("../"):
                return self.source

            else:
                return relpath

        return self.source

    @sourcerel.setter
    def sourcerel(self, value):
        if isinstance(value, (str, pathlib.Path)) and self.parent and self.parent.config:
            self.source = os.path.join(self.parent.config.workingdir, value)

        else:
            self.source = value

    @property
    def sourceabs(self):
        """Input file absolute path."""
        if isinstance(self.source, pathlib.Path):
            return os.path.abspath(self.source)

class Attachments(transcode.util.ChildList):
    def prepare(self, logfile=None):
        print("--- Attachments ---", file=logfile)
        return matroska.attachments.Attachments([attachment.prepare(logfile) for attachment in self])
