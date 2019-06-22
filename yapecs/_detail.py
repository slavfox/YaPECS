# Copyright (c) 2019 Slavfox
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
from abc import ABC, abstractmethod
from functools import reduce
from operator import or_, and_
from typing import Generic, Dict, Type, Iterable, NamedTuple, List, TypeVar, \
    Set, TYPE_CHECKING, Generator

if TYPE_CHECKING:
    from yapecs.component import Component
    from yapecs.world import World
    from yapecs.processor import Processor


class Bitmask(int):
    # Oh boy. Strap in, it's ugly hack time!
    #
    # Normally, typing.NewType would be perfect for Bitmasks - after all,
    # we never want to pass a random integer into a function expecting a
    # Bitmask. Aliasing `Bitmask = int` doesn't help us at all.
    # However, NewType has a big problem::
    #
    #     foo: Bitmask = Bitmask(0b10)
    #     foo |= 0b01  # error: Incompatible types in assignment (expression
    #                  # has type "int", variable has type "Bitmask")
    #     foo = Bitmask(foo | 0b01)  # ok
    #
    # Why is this a problem? Because explicitly casting to Bitmask is slooooow.
    # I'm not kidding. The last line is twice as slow as the previous one on
    # my machine. That's the last thing we want when we're already using
    # bitmasks for performance!
    #
    # So, here's where the ugly hack comes in. Mypy ignores `del`s,
    # so we let it know that `Bitmask(0b10) | 0b01` is still a valid
    # Bitmask, but we immediately delete the definition right afterwards -
    # so that at runtime, this entire class body is just::
    #
    #     class Bitmask(int):
    #         pass
    #
    # That way, it doesn't screech at us when we use bitwise operators,
    # but at the same time, it raises warnings when we try to use a Bitmask
    # improperly - eg. by adding to, or multiplying it - or when we pass a
    # naked `int` into a function expecting a Bitmask.
    #
    # Yay.
    def __lshift__(self, other) -> 'Bitmask': ...
    del __lshift__

    def __rshift__(self, other) -> 'Bitmask': ...
    del __rshift__

    def __and__(self, other) -> 'Bitmask': ...
    del __and__

    def __xor__(self, other) -> 'Bitmask': ...
    del __xor__

    def __or__(self, other) -> 'Bitmask': ...
    del __or__

    @property
    def bits(self) -> Generator['Bitmask', None, None]:
        bit = Bitmask(1)
        while bit <= self:
            if bit & self:
                yield bit
            bit <<= 1


class EntityID(int):
    # Ditto here
    def __add__(self, other) -> 'EntityID': ...
    del __add__


K = TypeVar('K')
V = TypeVar('V')


class InvariantDict(Generic[K, V], Dict[K, V], ABC):
    """
    A dict subclass that holds an invariant and rejects any mutation other
    than adding elements (without specifying the key). Subclasses should define
    get_new_key.
    """
    def __setitem__(self, key, value):
        raise TypeError(
            f"{self.__class__.__name__} does not support item assignment, "
            f"use .add() instead."
        )

    def update(self, *args, **kwargs) -> None:
        raise TypeError(
            f"{self.__class__.__name__} does not support .update(), use "
            f".add() instead."
        )

    def __delitem__(self, key):
        raise TypeError(
            f"{self.__class__.__name__} does not support key removal."
        )

    def setdefault(self, key, default=None):
        raise TypeError(
            f"{self.__class__.__name__} does not support .setitem(), use "
            f".getitem() instead."
        )

    def pop(self, key, default=None):
        raise TypeError(
            f"{self.__class__.__name__} does not support .pop()."
        )

    def popitem(self):
        raise TypeError(
            f"{self.__class__.__name__} does not support .popitem(). Use "
            f"reversed() instead."
        )

    def fromkeys(self, iterable, value=None):
        return self.__class__(dict.fromkeys(iterable, value))

    @abstractmethod
    def get_new_key(self, value: V) -> K:
        ...

    def add(self, value: V) -> K:
        key = self.get_new_key(value)
        dict.__setitem__(self, key, value)
        return key


class ComponentRegistry(InvariantDict[Type[Component], Bitmask]):
    def get_new_key(self, value):
        return 1 << len(self)


class EntityRecord(InvariantDict[Bitmask, Component], ABC):

    __slots__ = ('bitmask', 'id')

    @abstractmethod
    @property
    def _world(self) -> 'World': ...

    # noinspection PyShadowingBuiltins
    def __init__(
            self, id: EntityID, components: Iterable[Component] = ()
    ) -> None:
        super().__init__(
            {self._world._component_types[c.__class__]: c for c in components}
        )
        self.id = id
        self.bitmask: Bitmask = Bitmask(reduce(or_, self))

    def get_new_key(self, value: Component) -> Bitmask:
        return self._world._component_types[value.__class__]

    def add(self, value: Component) -> Bitmask:
        bitmask = self.get_new_key(value)
        dict.__setitem__(self, bitmask, value)
        self.bitmask |= bitmask
        return bitmask

    add_component = add

    def __delitem__(self, key: Bitmask):
        dict.__delitem__(self, key)
        self.bitmask ^= key

    def clear(self):
        dict.clear(self)
        self.bitmask &= 0

    def remove_component(self, comp_type: Type[Component]):
        del self[self._world._component_types[comp_type]]


class EntityCache(Dict[Bitmask, Set[EntityID]]):
    def __getitem__(self, bitmask: Bitmask) -> Set[EntityID]:
        return reduce(
            and_,
            (dict.__getitem__(self, bit) for bit in bitmask.bits)
        )


class ProcessorRecord(NamedTuple):
    processor: Processor
    component_bitmask: Bitmask
    order: List[Bitmask]
    priority: float = 0
