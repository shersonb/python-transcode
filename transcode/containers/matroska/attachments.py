import matroska.attachments
import transcode.util
from collections import OrderedDict, UserList
import pathlib
import mimetypes
import os

class AttachmentRef(object):
    from copy import copy

    def __init__(self, source, UID):
        self.source = source
        self.UID = UID

    def __reduce__(self):
        return self.__class__, (self.source, self.UID)

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

    def prepare(self, logfile=None):
        print(f"Attachment {self.UID}", file=logfile)

        if self.fileName:
            fileName = self.fileName

        elif isinstance(self.source, AttachmentRef):
            fileName = self.source.fileName

        elif isinstance(self.source, pathlib.Path):
            fileName = self.source.name

        print(f"    Filename: {fileName}", file=logfile)

        if self.mimeType:
            mimeType = self.mimeType

        elif isinstance(self.source, AttachmentRef):
            mimeType = self.source.mimeType

        elif isinstance(self.source, pathlib.Path):
            mimeType, encoding = mimetypes.MimeTypes().guess_type(str(self.source))

        print(f"    Mimetype: {mimeType}", file=logfile)

        if isinstance(self.source, AttachmentRef):
            attachment = self.source.attachment.copy()
            attachment.fileName = fileName
            attachment.mimeType = mimeType
            attachment.description = self.description
            attachment.fileUID = self.UID
            return attachment

        elif isinstance(self.source, pathlib.Path):
            attachment = matroska.attachments.AttachedFile.fromPath(str(self.source), mimeType, self.UID, self.description)
            attachment.fileName = fileName
            return attachment

    def __reduce__(self):
        return self.__class__, (self.UID, self.source), self.__getstate__()

    def __getstate__(self):
        state = OrderedDict()

        if self.fileName:
            state["fileName"] = self.fileName

        if self.mimeType:
            state["mimeType"] = self.mimeType

        if self.description:
            state["description"] = self.description

        return state

    def __setstate__(self, state):
        self.fileName = state.get("fileName")
        self.mimeType = state.get("mimeType")
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
