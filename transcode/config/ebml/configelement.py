from ebml.base import EBMLInteger, EBMLString, EBMLData, EBMLMasterElement, EBMLProperty, EBMLFloat, EBMLList, EBMLElement, Void
import ebml.serialization
import pathlib
import os

try:
    import lzma

except:
    lzma = None

try:
    import bz2

except:
    bz2 = None

try:
    import gzip

except:
    gzip = None

import transcode.config.obj
from transcode.config.ebml.inputfiles import InputFiles
from transcode.config.ebml.filterchains import FilterChains
from transcode.config.ebml.outputfiles import OutputFiles

class ConfigElement(ebml.serialization.Object):
    constructor = transcode.config.obj.Config
    ebmlID = b'\x13\xce\x86\xc9'
    __ebmlchildren__ = (
            EBMLProperty("objID", ebml.serialization.ObjID, optional=True),
            EBMLProperty("inputFiles", InputFiles),
            EBMLProperty("filterChains", FilterChains, optional=True),
            EBMLProperty("outputFiles", OutputFiles),
        )

    @classmethod
    def _createElement(cls, constructor, args, environ, refs):
        (path,) = args
        environ["cwd"] = path.parent
        self = cls.__new__(cls)
        return self

    def _saveState(self, state, environ, refs):
        environ["module"] = "transcode.containers"
        self.inputFiles = InputFiles.fromObj(state.get("input_files"), environ, refs)

        if state.get("filter_chains"):
            environ["module"] = "transcode.filters"
            self.filterChains = FilterChains.fromObj(state.get("filter_chains"), environ, refs)

        environ["module"] = "transcode.containers"
        self.outputFiles = OutputFiles.fromObj(state.pop("output_files"), environ, refs)

    def _constructArgs(self, environ, refs):
        configname = pathlib.Path(environ.get("configname", "untitled.ptc"))
        environ["cwd"] = configname.parent
        return (configname,)

    def _restoreState(self, obj, environ, refs):
        state = {}
        environ["module"] = "transcode.containers"
        state["input_files"] = self.inputFiles.toObj(environ, refs)

        if self.filterChains:
            environ["module"] = "transcode.filters"
            state["filter_chains"] = self.filterChains.toObj(environ, refs)

        environ["module"] = "transcode.containers"
        state["output_files"] = self.outputFiles.toObj(environ, refs)

        obj.__setstate__(state)

    @classmethod
    def load(cls, configname, file=None):
        configname = pathlib.Path(configname)
        #workingdir = configname.parent

        if file is None:
            if lzma and configname.suffix.upper() == ".XZ":
                file = lzma.LZMAFile(configname, "r")

            elif bz2 and configname.suffix.upper() == ".BZ2":
                file = bz2.BZ2File(configname, "r")

            elif gzip and configname.suffix.upper() == ".GZ":
                file = gzip.GzipFile(configname, "r")

            else:
                file = open(configname, "rb")

        self = cls.fromFile(file)
        return self.toObj({"configname": configname})

    @classmethod
    def save(cls, config, configname=None, file=None):
        if configname is not None:
            config.configname = configname

        self = cls.fromObj(config)

        if file is None:
            if lzma and config.configname.suffix.upper() == ".XZ":
                file = lzma.LZMAFile(config.configname, "w", preset=9|lzma.PRESET_EXTREME)

            elif bz2 and config.configname.suffix.upper() == ".BZ2":
                file = bz2.BZ2File(config.configname, "w", compresslevel=9)

            elif gzip and config.configname.suffix.upper() == ".GZ":
                file = gzip.GzipFile(config.configname, "w", compresslevel=9)

            else:
                file = open(config.configname, "wb")

        self.toFile(file)
