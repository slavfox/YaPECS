# Copyright (c) 2019 Slavfox
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
# Copyright (c) 2019 Slavfox
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
from functools import reduce
from operator import or_
from typing import Dict, Type, List, Callable, TYPE_CHECKING, \
    Iterable, Optional, Generator, Tuple

from yapecs._detail import ComponentRegistry, ProcessorRecord, EntityID, \
    EntityRecord as _EntityRecord, EntityCache

if TYPE_CHECKING:
    from yapecs.component import Component
    from yapecs.processor import Processor
    from yapecs._detail import Bitmask


class World:

    def __init__(self):

        class EntityRecord(_EntityRecord):
            _world = self

        self._entity_record_type = EntityRecord

        self._component_types: ComponentRegistry = ComponentRegistry()
        # int-keyed dicts are actually pretty fast, and strike a good
        # balance between speed and safety/ease of use when adding/deleting
        # components (as opposed to keeping a separate btree of bitmasks or
        # whatnot)
        self._entities: Dict[
            EntityID, EntityRecord
        ] = {}
        self._entity_cache: EntityCache = EntityCache()
        self._processors: List[ProcessorRecord] = []
        self._new_entity_id: EntityID = EntityID(0)

    def processor(
            self, *component_types: Type['Component'], priority: float = 0
    ) -> Callable[[Type['Processor']], Type['Processor']]:
        """Decorator to register a Processor."""
        def decorator(processor: Type['Processor']) -> Type['Processor']:
            for i, proc in enumerate(self._processors):
                if proc.priority < priority:
                    bitmasks = self._get_bitmasks(component_types)
                    self._processors.insert(
                        i,
                        ProcessorRecord(
                            processor(self),
                            reduce(or_, bitmasks),
                            bitmasks,
                            priority
                        )
                    )
                    break
            return processor
        return decorator

    def remove_processor(
            self, processor_type: Type['Processor'], priority: int = None
    ):
        self._processors = [
            record for record in self._processors
            if record.processor.__class__ == processor_type
            and (priority is None or record.priority == priority)
        ]

    def component(self, ctype: Type['Component']):
        """Decorator to register a Component type."""
        if self._processors:
            raise ValueError(f"Tried to register component '{ctype}' to a "
                             f"World '{self}' after registering a processor. "
                             f"All components must be registered before "
                             f"registering Processors.")

        self._component_types[1 << len(self._component_types)] = ctype

    def _get_bitmasks(
            self, component_types: Iterable[Type['Component']]
    ) -> List['Bitmask']:
        """
        Return a list of bitmasks such that the n-th element of the list is
        the bitmask for the n-th Component in the argument.
        """
        try:
            bitmasks = [self._component_types[ct] for ct in component_types]
        except KeyError as e:
            raise KeyError(
                f"Attempted to register Processor for "
                f"unregistered component type '{e.args[0].__name__}' "
                f"with World '{self}'. All components must be registered "
                f"before registering Processors."
            )
        else:
            return bitmasks

    def create_entity(self, *components: 'Component') -> EntityID:
        entity_id = self._new_entity_id
        record = self._entity_record_type(
            entity_id,
            components
        )
        self._entities[entity_id] = record

        # This, is PyCharm not supporting PEP-526 properly.
        # noinspection PyUnusedLocal
        bitmask: 'Bitmask'

        # For some reason, PyCharm screeches about expecting an iterable here.
        # It seems very much like a false postive, considering that
        # EntityRecord is a subclass of Dict.
        # noinspection PyTypeChecker
        for bitmask in record:
            self._entity_cache.setdefault(bitmask, set()).add(entity_id)

        self._new_entity_id += 1
        return entity_id

    def remove_entity(self, entity_id: EntityID):
        # See comment in create_entity
        # noinspection PyUnusedLocal
        bitmask: 'Bitmask'
        # noinspection PyTypeChecker
        for bitmask in self._entities[entity_id]:
            self._entity_cache[bitmask].remove(entity_id)
        del self._entities[entity_id]

    def get_entities_by_bitmask(
            self, bitmask: 'Bitmask'
    ) -> Generator[_EntityRecord, None, None]:
        yield from (
            self._entities[ent_id] for ent_id in self._entity_cache[bitmask]
        )

    def get_entity(self, entity_id: EntityID) -> Optional['_EntityRecord']:
        return self._entities.get(entity_id)

    def add_components(
            self, entity_id: EntityID, *components: Component
    ):
        record = self._entities[entity_id]
        for component in components:
            bitmask = record.add(component)
            self._entity_cache.setdefault(bitmask, set()).add(entity_id)

    def remove_components(
            self, entity_id: EntityID, *comp_types: Type[Component]
    ):
        record = self._entities[entity_id]
        for ctype in comp_types:
            bitmask: 'Bitmask' = self._component_types[ctype]
            del record[bitmask]
            self._entity_cache[bitmask].remove(entity_id)

    def get_components(
            self, entity_id: EntityID, *component_types: Type[Component]
    ) -> Tuple[Component, ...]:
        return tuple(
            self._entities[entity_id][self._component_types[ctype]]
            for ctype in component_types
        )

    def clear(self):
        self._component_types = ComponentRegistry()
        self._entities = {}
        self._entity_cache: EntityCache = EntityCache()
        self._processors: List[ProcessorRecord] = []
        self._new_entity_id: EntityID = EntityID(0)
