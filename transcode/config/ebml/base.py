from ebml.base import EBMLInteger, EBMLString, EBMLData, EBMLMasterElement, EBMLProperty, EBMLFloat, EBMLList, EBMLElement, Void
from ebml.ndarray import EBMLNDArray
from ebml.serialization import Object, List
from transcode.util import llist, ChildList, WeakRefList
from ..obj import InputFileList, OutputFileList, FilterList
import numpy
import pathlib
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


Object.registerType(numpy.ndarray, ArrayValue)
Object.registerType(pathlib.Path, PathElement)
Object.registerType(pathlib.PosixPath, PathElement)
Object.registerType(pathlib.WindowsPath, PathElement)
Object.registerType(pathlib.PurePosixPath, PathElement)
Object.registerType(pathlib.PurePath, PathElement)
Object.registerType(pathlib.PureWindowsPath, PathElement)
Object.registerType(llist, List)
Object.registerType(ChildList, List)
Object.registerType(InputFileList, List)
Object.registerType(OutputFileList, List)
Object.registerType(FilterList, List)
Object.registerType(WeakRefList, List)
