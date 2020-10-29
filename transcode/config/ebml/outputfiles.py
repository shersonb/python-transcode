from ebml.base import EBMLString, EBMLProperty
import ebml.serialization
from .base import PathElement
from .filterchains import FilterChainElement
from transcode import encoders, containers


class EncoderName(EBMLString):
    ebmlID = b"\x7f\xa7"


class Encoder(ebml.serialization.Object):
    ebmlID = b"\x42\x85"
    module = encoders
    __ebmlchildren__ = (
        EBMLProperty("constructor", ebml.serialization.Constructor),
        EBMLProperty("name", EncoderName, optional=True),
        EBMLProperty("options", (ebml.serialization.State,
                                 ebml.serialization.StateDict), optional=True),
    )

    def _constructArgs(self, environ, refs):
        if self.name:
            return (self.name,)

        return ()

    @classmethod
    def _createArgsElement(cls, args, environ, refs):
        if len(args) == 1:
            (name,) = args
            return dict(name=name)

        return ()

    def _saveState(self, state, environ, refs):
        if isinstance(state, dict):
            self.options = ebml.serialization.StateDict.fromObj(
                state, environ, refs)

        else:
            self.options = ebml.serialization.State.fromObj(
                state, environ, refs)

    def _restoreState(self, obj, environ, refs):
        if self.options:
            obj.__setstate__(self.options.toObj(environ, refs))


class TrackName(EBMLString):
    ebmlID = b"\x64\xcd"


class Language(EBMLString):
    ebmlID = b"\x42\x78"


class OutputTrack(ebml.serialization.Object):
    ebmlID = b"\x55\xc4"
    module = containers
    __ebmlchildren__ = (
        EBMLProperty("objID", ebml.serialization.ObjID, optional=True),
        EBMLProperty("source", ebml.serialization.Ref, optional=True),
        EBMLProperty("encoder", Encoder, optional=True),
        EBMLProperty("filters", FilterChainElement, optional=True),
        EBMLProperty("name", TrackName, optional=True),
        EBMLProperty("language", Language, optional=True),
        EBMLProperty("options", ebml.serialization.StateDict, optional=True),
    )

    @classmethod
    def _createConstructorElement(cls, constructor, environ, refs):
        return None

    @classmethod
    def _createArgsElement(cls, args, environ, refs):
        (source,) = args
        d = dict()

        if id(source) in refs:
            d["source"] = refs[id(source)]

        return d

    def _getConstructor(self, environ):
        return environ.get("trackclass")

    def _constructArgs(self, environ, refs):
        source = refs.get(self.source)

        return (source,)

    def _saveState(self, state, environ, refs):
        mod = environ.get("module")

        if "encoder" in state:
            environ["module"] = "transcode.encoders"
            self.encoder = Encoder.fromObj(state.pop("encoder"), environ, refs)

        if "filters" in state:
            environ["module"] = "transcode.filters"
            self.filters = FilterChainElement.fromObj(
                state.pop("filters"), environ, refs)

        if mod:
            environ["module"] = mod

        elif "module" in environ:
            del environ["module"]

        self.options = ebml.serialization.StateDict.fromObj(
            state, environ, refs)

    def _restoreState(self, obj, environ, refs):
        if self.options:
            state = self.options.toObj(environ, refs)

        else:
            state = {}

        mod = environ.get("module")

        if self.encoder:
            environ["module"] = "transcode.encoders"
            state["encoder"] = self.encoder.toObj(environ, refs)

        if self.filters:
            environ["module"] = "transcode.filters"
            state["filters"] = self.filters.toObj(environ, refs)

        if mod:
            environ["module"] = mod

        elif "module" in environ:
            del environ["module"]

        obj.__setstate__(state)


class OutputTracks(ebml.serialization.List):
    ebmlID = b"\x50\x7c"
    _typeMap = {object: OutputTrack}
    _typesByID = {OutputTrack.ebmlID: OutputTrack}


class OutputPath(PathElement):
    ebmlID = b"\x4c\x3f"


class OutputFile(ebml.serialization.Object):
    ebmlID = b"\x33\xe6\xfe"
    module = containers

    __ebmlchildren__ = (
        EBMLProperty("constructor", ebml.serialization.Constructor),
        EBMLProperty("objID", ebml.serialization.ObjID, optional=True),
        EBMLProperty("outputPath", OutputPath),
        EBMLProperty("tracks", OutputTracks, optional=True),
        EBMLProperty("options", (ebml.serialization.State,
                                 ebml.serialization.StateDict), optional=True),
    )

    @classmethod
    def _createArgsElement(cls, args, environ, refs):
        (path,) = args
        return dict(outputPath=cls.outputPath.cls.fromObj(path, environ, refs))

    def _saveState(self, state, environ, refs):
        self.tracks = self.__class__.tracks.cls.fromObj(
            state.pop("tracks"), environ, refs)
        self.options = ebml.serialization.StateDict.fromObj(
            state, environ, refs)

    def _constructArgs(self, environ, refs):
        return (self._outputPath.toObj(environ, refs),)

    def _restoreState(self, obj, environ, refs):
        state = {}
        environ["trackclass"] = obj.trackclass
        state["tracks"] = self.tracks.toObj(environ, refs)

        if self.options:
            state.update(self.options.toObj(environ, refs))

        obj.__setstate__(state)


class OutputFiles(ebml.serialization.List):
    ebmlID = b"\x20\xc4\xd5"
    _typeMap = {object: OutputFile}
    _typesByID = {OutputFile.ebmlID: OutputFile}
