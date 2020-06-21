from collections import OrderedDict
import pathlib
import os

class Config(object):
    def __init__(self, configname, input_files=[], filter_chains=[], output_files=[]):
        self.configname = configname
        self.input_files = input_files
        self.filter_chains = filter_chains
        self.output_files = output_files

        for file in input_files:
            file.config = self

        for file in output_files:
            file.config = self

    @property
    def configname(self):
        return self._configname

    @configname.setter
    def configname(self, value):
        self._configname = pathlib.Path(value)

    @property
    def workingdir(self):
        return self.configname.parent

    @property
    def configstem(self):
        if self.configname.suffix.upper() in (".XZ", ".BZ2", ".GZ"):
            configname = pathlib.Path(self.configname.stem)

        else:
            configname = self.configname

        if configname.suffix.upper() == ".PTC":
            return self.workingdir.joinpath(configname.stem)

        return self.workingdir.joinpath(configname)

    def __reduce__(self):
        return self.__class__, (self._configname,), self.__getstate__()

    def __getstate__(self):
        d = OrderedDict()
        d["input_files"] = self.input_files
        d["filter_chains"] = self.filter_chains
        d["output_files"] = self.output_files
        return d

    def __setstate__(self, state):
        self.input_files = state.get("input_files")

        for file in self.input_files:
            file.config = self

        self.filter_chains = state.get("filter_chains")
        self.output_files = state.get("output_files")

        for file in self.output_files:
            file.config = self
