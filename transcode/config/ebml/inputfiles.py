from ebml.base import EBMLInteger, EBMLString, EBMLData, EBMLMasterElement, EBMLProperty, EBMLFloat, EBMLList, EBMLElement, Void
from ebml.ndarray import EBMLNDArray
from ebml.util import toVint, fromVint, parseVints
import ebml.serialization
from fractions import Fraction as QQ
import numpy
import pathlib
import transcode.config.obj
import importlib
import types
from transcode.config.ebml.base import ArrayValue, PathElement

class InputTrack(ebml.serialization.Object):
    ebmlID = b"\x5b\xda"
    module = transcode.containers
    __ebmlchildren__ = (
            EBMLProperty("objID", ebml.serialization.ObjID, optional=True),
            EBMLProperty("state", (ebml.serialization.State, ebml.serialization.StateDict), optional=True),
        )

    @classmethod
    def _createConstructorElement(cls, constructor, environ, refs):
        return None

    def _getConstructor(self, environ):
        return environ.get("trackclass")

    def _createArgsElement(self, environ, refs):
        return ()

    def _constructArgs(self, environ, refs):
        return ()

InputTrack.registerType(numpy.ndarray, ArrayValue)

class InputTracks(ebml.serialization.List):
    ebmlID = b"\x47\xfd"
    _typeMap = {object: InputTrack}
    _typesByID = {InputTrack.ebmlID: InputTrack}

class InputPath(PathElement):
    ebmlID = b"\x48\x4f"

class InputFile(ebml.serialization.Object):
    ebmlID = b"\x31\xbc\xac"
    module = transcode.containers
    __ebmlchildren__ = (
            EBMLProperty("objID", ebml.serialization.ObjID, optional=True),
            EBMLProperty("constructor", ebml.serialization.Constructor),
            EBMLProperty("inputPath", InputPath),
            EBMLProperty("tracks", InputTracks, optional=True),
            EBMLProperty("state", ebml.serialization.StateDict, optional=True),
        )

    @classmethod
    def _createArgsElement(cls, args, environ, refs):
        (inputPath,) = args
        return cls.inputPath.cls.fromObj(inputPath, environ, refs)

    def _saveState(self, state, environ, refs):
        self.tracks = self.__class__.tracks.cls.fromObj(state.pop("tracks"), environ, refs)
        self.state = self.__class__.state.cls.fromObj(state, environ, refs)

    def _constructArgs(self, environ, refs):
        return (self._inputPath.toObj(environ, refs),)

    def _restoreState(self, obj, environ, refs):
        environ["trackclass"] = obj.trackclass

        if self.state:
            state = self.state.toObj(environ, refs)

        else:
            state = {}

        state["tracks"] = self.tracks.toObj(environ, refs)
        obj.__setstate__(state)

class InputFiles(ebml.serialization.List):
    ebmlID = b"\x22\xad\xc9"
    _typeMap = {object: InputFile}
    _typesByID = {InputFile.ebmlID: InputFile}

