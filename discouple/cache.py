from abc import ABC
from enum import Enum


class EntityType(Enum):
    GUILD = 0
    CHANNEL = 1
    ROLE = 2
    USER = 3
    MEMBER = 4


class EntityCache(ABC):
    """
    Responsible for storing discord entities like guilds, roles and channels
    The logic for getting and setting values is encapsulated to make subclassing easier
    """
    async def _set_json(self, entity_type: EntityType, entity_id: int, data: dict) -> dict:
        pass

    async def _get_json(self, entity_type: EntityType, entity_id: int) -> dict:
        pass

    async def _get_entity_ids(self, entity_type: EntityType) -> list:
        pass

    async def get_guild(self, guild_id: int) -> dict:
        return await self._get_json(EntityType.GUILD, guild_id)

    async def iter_guilds(self):
        for guild_id in await self._get_entity_ids(EntityType.GUILD):
            guild = await self._get_json(EntityType.GUILD, guild_id)
            if guild:
                yield guild
