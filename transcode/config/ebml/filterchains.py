from ebml.base import EBMLInteger, EBMLString, EBMLData, EBMLMasterElement, EBMLProperty, EBMLFloat, EBMLList, EBMLElement, Void
from ebml.ndarray import EBMLNDArray
from ebml.util import toVint, fromVint, parseVints
import ebml.serialization
from fractions import Fraction as QQ
import numpy
import pathlib
#import transcode.config.obj
#import transcode.filters
from ...filters.filterchain import FilterChain
from ...filters.concatenate import Concatenate
import importlib
import types
from .base import ArrayValue

class SrcStart(EBMLInteger):
    ebmlID = b"\x41\x03"

class ZoneElement(ebml.serialization.Object):
    ebmlID = b"\x41\x02"
    __ebmlchildren__ = (
            EBMLProperty("srcStart", SrcStart),
            EBMLProperty("options", (ebml.serialization.State, ebml.serialization.StateDict), optional=True),
        )

    @classmethod
    def _createConstructorElement(cls, constructor, environ, refs):
        return None

    def _getConstructor(self, environ):
        return environ.get("zoneclass")

    @classmethod
    def _createArgsElement(cls, args, environ, refs):
        return SrcStart(*args)

    def _constructArgs(self, environ, refs):
        return (self.srcStart,)

    def _saveState(self, state, environ, refs):
        if isinstance(state, dict):
            self.options = ebml.serialization.StateDict.fromObj(state, environ, refs)

        else:
            self.options = ebml.serialization.State.fromObj(state, environ, refs)

    def _restoreState(self, obj, environ, refs):
        if self.options:
            obj.__setstate__(self.options.toObj(environ, refs))

class Zones(ebml.serialization.List):
    ebmlID = b"\x41\x04"
    _typesByID = {ZoneElement.ebmlID: ZoneElement}

class FilterElement(ebml.serialization.Object):
    ebmlID = b"\x31\xbc\xac"
    __ebmlchildren__ = (
            EBMLProperty("objID", ebml.serialization.ObjID, optional=True),
            EBMLProperty("prev", ebml.serialization.Ref, optional=True),
            EBMLProperty("constructor", ebml.serialization.Constructor),
            EBMLProperty("options", (ebml.serialization.State, ebml.serialization.StateDict), optional=True),
            EBMLProperty("zones", Zones, optional=True)
        )

    @classmethod
    def _createArgsElement(cls, args, environ, refs):
        return ()

    def _constructArgs(self, environ, refs):
        return ()

    def _saveState(self, state, environ, refs):
        if "prev" in state:
            prev = state.pop("prev")
            self.prev = ebml.serialization.Ref(refs[id(prev)])

        if isinstance(state, dict):
            self.options = ebml.serialization.StateDict.fromObj(state, environ, refs)

        else:
            self.options = ebml.serialization.State.fromObj(state, environ, refs)

    def _restoreState(self, obj, environ, refs):
        if self.options:
            state = self.options.toObj(environ, refs)

        else:
            state = {}

        if self.prev is not None:
            state.update(prev=refs[self.prev])

        obj.__setstate__(state)

    def _restoreItems(self, obj, environ, refs):
        if hasattr(obj, "zoneclass"):
            environ["zoneclass"] = obj.zoneclass

        elif "zoneclass" in environ:
            del environ["zoneclass"]

        if self.zones:
            zones = self.zones.toObj(environ, refs)
            obj.extend(zones)

    def _saveItems(self, items, environ, refs):
        self.zones = Zones(items=[], parent=self)

        for zone in items:
            zone = ZoneElement.fromObj(zone, environ, refs)
            self.zones.append(zone)

class SubFilter(ebml.serialization.Object):
    ebmlID = b"\x31\xbc\xac"
    __ebmlchildren__ = (
            EBMLProperty("constructor", ebml.serialization.Constructor),
            EBMLProperty("options", (ebml.serialization.State, ebml.serialization.StateDict), optional=True),
            EBMLProperty("zones", Zones, optional=True)
        )

    @classmethod
    def _createArgsElement(cls, args, environ, refs):
        return ()

    def _constructArgs(self, environ, refs):
        return ()

    def _saveState(self, state, environ, refs):
        if "prev" in state:
            del state["prev"]

        if isinstance(state, dict):
            self.options = ebml.serialization.StateDict.fromObj(state, environ, refs)

        else:
            self.options = ebml.serialization.State.fromObj(state, environ, refs)

    def _restoreState(self, obj, environ, refs):
        if self.options:
            state = self.options.toObj(environ, refs)
            obj.__setstate__(state)

    def _restoreItems(self, obj, environ, refs):
        if hasattr(obj, "zoneclass"):
            environ["zoneclass"] = obj.zoneclass

        elif "zoneclass" in environ:
            del environ["zoneclass"]

        if self.zones:
            zones = self.zones.toObj(environ, refs)
            obj.extend(zones)

    def _saveItems(self, items, environ, refs):
        self.zones = Zones(items=[], parent=self)

        for zone in items:
            zone = ZoneElement.fromObj(zone, environ, refs)
            self.zones.append(zone)

class Filters(EBMLList):
    itemclass = (FilterElement, SubFilter)

class FilterChainElement(ebml.serialization.Object):
    ebmlID = b"\x22\xad\xc9"
    constructor = FilterChain
    _typeMap = {object: SubFilter}
    _typesByID = {SubFilter.ebmlID: FilterElement}
    __ebmlchildren__ = (
            EBMLProperty("objID", ebml.serialization.ObjID, optional=True),
            EBMLProperty("prev", ebml.serialization.Ref, optional=True),
            EBMLProperty("filters", Filters, optional=True),
        )

    @classmethod
    def _createElement(cls, constructor, args, environ, refs):
        return cls()

    def _constructArgs(self, environ, refs):
        return ()

    def _restoreState(self, obj, environ, refs):
        prev = refs.get(self.prev)
        obj.__setstate__({"prev": prev})

    def _restoreItems(self, obj, environ, refs):
        if self.filters:
            filters = [filter.toObj(environ, refs) for filter in self.filters]
            obj.extend(filters)

    def _saveState(self, state, environ, refs):
        if isinstance(state, dict) and id(state.get("prev")) in refs:
            self.prev = ebml.serialization.Ref(refs[id(state.get("prev"))])

    def _saveItems(self, items, environ, refs):
        self.filters = Filters(items=[])

        for filter in items:
            filter = SubFilter.fromObj(filter, environ, refs)
            self.filters.append(filter)

class Refs(EBMLList):
    itemclass = ebml.serialization.Ref

class ConcatenateElement(ebml.serialization.Object):
    ebmlID = b"\x2a\xcf\xc0"
    constructor = Concatenate
    _typeMap = {object: FilterElement}
    _typesByID = {FilterElement.ebmlID: FilterElement}
    __ebmlchildren__ = (
            EBMLProperty("objID", ebml.serialization.ObjID, optional=True),
            EBMLProperty("options", (ebml.serialization.State, ebml.serialization.StateDict), optional=True),
            EBMLProperty("segments", Refs, optional=True),
        )

    @classmethod
    def _createElement(cls, constructor, args, environ, refs):
        return cls()

    def _constructArgs(self, environ, refs):
        return ()

    def _restoreState(self, obj, environ, refs):
        if self.options:
            obj.__setstate__(self.options.toObj(environ, refs))


    def _restoreItems(self, obj, environ, refs):
        if self.segments:
            segments = [refs[ref] for ref in self.segments]
            obj.extend(segments)

    def _saveState(self, state, environ, refs):
        if isinstance(state, dict):
            self.options = ebml.serialization.StateDict.fromObj(state, environ, refs)

        else:
            self.options = ebml.serialization.State.fromObj(state, environ, refs)

    def _saveItems(self, items, environ, refs):
        self.segments = Refs(items=[])

        for segment in items:
            segment = ebml.serialization.Ref(refs[id(segment)])
            self.segments.append(segment)

class FilterChains(ebml.serialization.List):
    ebmlID = b"\x25\x7b\xcc"
    _typeMap = {FilterChain: FilterChainElement, Concatenate: ConcatenateElement, object: FilterElement}
    _typesByID = {FilterChainElement.ebmlID: FilterChainElement, FilterElement.ebmlID: FilterElement, ConcatenateElement.ebmlID: ConcatenateElement}

