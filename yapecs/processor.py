# Copyright (c) 2019 Slavfox
#
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at https://mozilla.org/MPL/2.0/.
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from yapecs.component import Component
    from yapecs.world import World


class Processor(ABC):
    __slots__ = ('world',)

    def __init__(self, world: 'World') -> None:
        self.world: 'World' = world

    @abstractmethod
    def process(self, entity: int, *components: 'Component'):
        raise NotImplementedError
