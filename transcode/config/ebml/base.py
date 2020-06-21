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
import os

class ArrayValue(EBMLNDArray):
    ebmlID = b"\x40\x88"

class PathElement(EBMLString):
    ebmlID = b"\x75\xd6"

    @classmethod
    def fromObj(cls, obj, environ=None, refs=None):
        if refs is None:
            refs = {}

        if environ is None:
            environ = {}

        workingdir = environ.get("cwd", os.getcwd())
        relpath = os.path.relpath(obj, workingdir)

        if not relpath == os.path.pardir and not relpath.startswith(f"{os.path.pardir}{os.path.sep}"):
            return cls(relpath)

        return cls(obj)

    def toObj(self, environ, refs):
        workingdir = environ.get("cwd", os.getcwd())
        return os.path.join(workingdir, self.data)

ebml.serialization.Object.registerType(numpy.ndarray, ArrayValue)
ebml.serialization.Object.registerType(pathlib.Path, PathElement)
ebml.serialization.Object.registerType(pathlib.PosixPath, PathElement)
ebml.serialization.Object.registerType(pathlib.WindowsPath, PathElement)
ebml.serialization.Object.registerType(pathlib.PurePosixPath, PathElement)
ebml.serialization.Object.registerType(pathlib.PurePath, PathElement)
ebml.serialization.Object.registerType(pathlib.PureWindowsPath, PathElement)
