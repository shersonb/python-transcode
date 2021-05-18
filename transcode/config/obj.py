from collections import OrderedDict, UserList
import pathlib
import os


class FileList(UserList):
    def __init__(self, items=[], config=None):
        self.data = list(items)
        self.config = config

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        for item in self:
            item.config = value

        self._config = value

    def append(self, item):
        item.config = self.config
        super().append(item)

    def insert(self, index, item):
        item.config = self.config
        super().insert(index, item)

    def extend(self, items):
        k = len(self)
        super().extend(items)

        for item in self[k:]:
            item.config = self.config

    def __setitem__(self, index, item):
        if isinstance(index, int):
            item.config = self.config

        elif isinstance(index, slice):
            item = list(item)

            for subitem in item:
                subitem.config = self.config

        super().__setitem__(index, item)

    def __reduce__(self):
        state = self.__getstate__()

        if state:
            return self.__class__, (), state, iter(self)

        return self.__class__, (), None, iter(self)

    def __getstate__(self):
        return


class InputFileList(FileList):
    pass


class OutputFileList(FileList):
    pass


class FilterList(UserList):
    def __init__(self, items=[], config=None):
        self.data = list(items)
        self.config = config

    def append(self, item):
        item.parent = self
        super().append(item)

    def insert(self, index, item):
        item.parent = self
        super().insert(index, item)

    def extend(self, items):
        k = len(self)
        super().extend(items)

        for item in self[k:]:
            item.parent = self

    def __setitem__(self, index, item):
        if isinstance(index, int):
            item.parent = self

        elif isinstance(index, slice):
            item = list(item)

            for subitem in item:
                subitem.parent = self

        super().__setitem__(index, item)

    def __reduce__(self):
        state = self.__getstate__()

        if state:
            return self.__class__, (), state, iter(self)

        return self.__class__, (), None, iter(self)

    def __getstate__(self):
        return


class Config(object):
    def __init__(self, configname=None, input_files=[], filter_chains=[],
                 output_files=[]):
        self.configname = configname
        self.input_files = input_files
        self.filter_chains = filter_chains
        self.output_files = output_files

        for file in input_files:
            file.config = self

        for file in output_files:
            file.config = self

    @property
    def input_files(self):
        return self._input_files

    @input_files.setter
    def input_files(self, value):
        self._input_files = InputFileList(value, self)

    @property
    def filter_chains(self):
        return self._filter_chains

    @filter_chains.setter
    def filter_chains(self, value):
        self._filter_chains = FilterList(value or [], self)

    @property
    def output_files(self):
        return self._output_files

    @output_files.setter
    def output_files(self, value):
        self._output_files = OutputFileList(value, self)

    @property
    def configname(self):
        return self._configname

    @configname.setter
    def configname(self, value):
        if value is not None:
            self._configname = pathlib.Path(value)

        else:
            self._configname = None

    @property
    def workingdir(self):
        if self.configname is not None:
            return self.configname.parent

        return os.getcwd()

    @property
    def configstem(self):
        if self.configname is None:
            return

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
        d["input_files"] = self.input_files.data
        d["filter_chains"] = self.filter_chains.data
        d["output_files"] = self.output_files.data
        return d

    def __setstate__(self, state):
        self.input_files = state.get("input_files")

        for file in self.input_files:
            file.config = self

        self.filter_chains = state.get("filter_chains")
        self.output_files = state.get("output_files")

        for file in self.output_files:
            file.config = self
