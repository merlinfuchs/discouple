import asyncio

from abc import ABC
from collections import defaultdict

import orjson

from .enums import ChannelType

__all__ = ("EntityCache", "NoEntityCache", "LocalEntityCache", "RedisEntityCache")


class EntityCache(ABC):
    """
    Responsible for storing discord entities like guilds, roles and channels
    Everything is async to support a distributed cache
    """

    async def store_guild(self, data):
        pass

    async def get_guild(self, guild_id):
        pass

    async def remove_guild(self, guild_id):
        pass

    async def iter_guilds(self):
        pass

    async def store_channel(self, data):
        pass

    async def get_channel(self, channel_id):
        pass

    async def remove_channel(self, channel_id):
        pass

    async def iter_channels(self):
        pass

    async def iter_guild_channels(self, guild_id):
        pass

    async def store_role(self, data):
        pass

    async def get_role(self, role_id):
        pass

    async def remove_role(self, role_id):
        pass

    async def iter_roles(self):
        pass

    async def iter_guild_roles(self, guild_id):
        pass

    async def store_user(self, data):
        pass

    async def get_user(self, user_id):
        pass

    async def remove_user(self, user_id):
        pass

    async def iter_users(self):
        pass

    async def store_member(self, data):
        pass

    async def get_member(self, guild_id, user_id):
        pass

    async def remove_member(self, guild_id, user_id):
        pass

    async def iter_guild_members(self, guild_id):
        pass


class NoEntityCache(EntityCache):
    pass


class LocalEntityCache(EntityCache):
    def __init__(self):
        self.guilds = {}
        self.channels = {}
        self.users = {}
        self.roles = {}
        self.members = defaultdict(dict)

    async def store_guild(self, data):
        self.guilds[data["id"]] = data

    async def get_guild(self, guild_id):
        return self.guilds.get(guild_id)

    async def remove_guild(self, guild_id):
        try:
            del self.guilds[guild_id]
        except KeyError:
            pass

    async def iter_guilds(self):
        for guild in self.guilds.values():
            yield guild

    async def store_channel(self, data):
        self.channels[data["id"]] = data

    async def get_channel(self, channel_id):
        return self.channels.get(channel_id)

    async def remove_channel(self, channel_id):
        try:
            del self.channels[channel_id]
        except KeyError:
            pass

    async def iter_channels(self):
        for channel in self.channels.values():
            yield channel

    async def iter_guild_channels(self, guild_id):
        guild_id = f"{guild_id}"
        for channel in self.channels.values():
            if channel["guild_id"] == guild_id:
                yield channel

    async def store_role(self, data):
        self.roles[data["id"]] = data

    async def get_role(self, role_id):
        return self.roles.get(role_id)

    async def remove_role(self, role_id):
        try:
            del self.roles[role_id]
        except KeyError:
            pass

    async def iter_roles(self):
        for role in self.roles.values():
            yield role

    async def iter_guild_roles(self, guild_id):
        guild_id = f"{guild_id}"
        for role in self.roles.values():
            if role["guild_id"] == guild_id:
                yield role

    async def store_user(self, data):
        self.users[data["id"]] = data

    async def get_user(self, user_id):
        return self.users.get(user_id)

    async def remove_user(self, user_id):
        try:
            del self.users[user_id]
        except KeyError:
            pass

    async def iter_users(self):
        for user in self.users.values():
            yield user

    async def store_member(self, data):
        self.members[int(data["guild_id"])][int(data["user"]["id"])] = data

    async def get_member(self, guild_id, member_id):
        return self.members[guild_id].get(member_id)

    async def remove_member(self, guild_id, member_id):
        try:
            del self.members[guild_id][member_id]
        except KeyError:
            pass

    async def iter_guild_members(self, guild_id):
        for member in self.members[guild_id].values():
            yield member


class RedisEntityCache(EntityCache):
    """
    Entity cache implemented using RedisJSON
    https://oss.redislabs.com/redisjson/

    Some notes for development:
        - Return values from JSON.GET are bytes
        - JSON.GET returns None if no key
    """

    def __init__(self, redis, prefix="dc"):
        self.redis = redis
        self.prefix = prefix
        asyncio.create_task(self.init_json())

    async def init_json(self):
        for type_ in ("guild", "channel", "role", "user"):
            if not await self.redis.execute("EXISTS", f"{self.prefix}:{type_}s"):
                await self.redis.execute(
                    "JSON.SET", f"{self.prefix}:{type_}s", ".", b"{}"
                )

    # Most entities are based on a simple ID for identifying

    async def store_entity(self, type_, data):
        id_ = f"{data['id']}"
        await self.redis.execute(
            "JSON.SET", f"{self.prefix}:{type_}s", id_, orjson.dumps(data)
        )
        if type_ == "guild":
            if not await self.redis.execute(
                "EXISTS", f"{self.prefix}:guild:{id_}:members"
            ):
                await self.redis.execute(
                    "JSON.SET", f"{self.prefix}:guild:{id_}:members", ".", b"{}"
                )
        if type_ in ("channel", "role") and data.get("type") not in (
            ChannelType.DM,
            ChannelType.GROUP_DM,
        ):
            # We need a set for storing members of the guild
            await self.redis.execute(
                "SADD", f"{self.prefix}:{data['guild_id']}:{type_}s", id_
            )

    async def get_entity(self, type_, entity_id):
        data = await self.redis.execute(
            "JSON.GET", f"{self.prefix}:{type_}s", entity_id
        )
        if not data:
            return None
        return orjson.loads(data)

    async def remove_entity(self, type_, entity_id):
        id_ = f"{entity_id}"
        # We need to fetch the JSON for the guild ID if it's a channel or role
        if type_ in ("channel", "role"):
            data = orjson.loads(
                await self.redis.execute("JSON.GET", f"{self.prefix}:{type_}s", id_)
            )
        await self.redis.execute("JSON.DEL", f"{self.prefix}:{type_}s", id_)
        if type_ in ("channel", "role") and data.get("type") not in (
            ChannelType.DM,
            ChannelType.GROUP_DM,
        ):
            # We need a set for storing members of the guild
            # DM channels (1, 3) will be ignored
            await self.redis.execute(
                "SREM", f"{self.prefix}:{data['guild_id']}:{type_}s", id_
            )

    async def iter_entities(self, type_):
        for key in await self.redis.execute(
            "JSON.OBJKEYS", f"{self.prefix}:{type}s", "."
        ):
            yield orjson.loads(
                await self.redis.execute("JSON.GET", f"{self.prefix}:{type_}s", key)
            )

    async def iter_guild_entities(self, guild_id, type_):
        for key in await self.redis.execute(
            "SMEMBERS", f"{self.prefix}:{guild_id}:{type_}s"
        ):
            yield orjson.loads(
                await self.redis.execute("JSON.GET", f"{self.prefix}:{type_}s", key)
            )

    def store_guild(self, data):
        return self.store_entity("guild", data)

    def get_guild(self, guild_id):
        return self.get_entity("guild", guild_id)

    def remove_guild(self, guild_id):
        return self.remove_entity("guild", guild_id)

    def iter_guilds(self):
        return self.iter_entities("guild")

    def store_channel(self, data):
        return self.store_entity("channel", data)

    def get_channel(self, channel_id):
        return self.get_entity("channel", channel_id)

    def remove_channel(self, channel_id):
        return self.remove_entity("channel", channel_id)

    def iter_channels(self):
        return self.iter_entities("channel")

    def iter_guild_channels(self, guild_id):
        return self.iter_guild_entities(guild_id, "channel")

    def store_role(self, data):
        return self.store_entity("role", data)

    def get_role(self, channel_id):
        return self.get_entity("role", channel_id)

    def remove_role(self, channel_id):
        return self.remove_entity("role", channel_id)

    def iter_roles(self):
        return self.iter_entities("role")

    def iter_guild_roles(self, guild_id):
        return self.iter_guild_entities(guild_id, "role")

    def store_user(self, data):
        return self.store_entity("user", data)

    def get_user(self, channel_id):
        return self.get_entity("user", channel_id)

    def remove_user(self, channel_id):
        return self.remove_entity("user", channel_id)

    def iter_users(self):
        return self.iter_entities("user")

    # Members require special treatment

    async def store_member(self, data):
        id_ = f"{data['user']['id']}"
        await self.redis.execute(
            "JSON.SET",
            f"{self.prefix}:guild:{data['guild_id']}:members",
            id_,
            orjson.dumps(data),
        )

    async def get_member(self, guild_id, user_id):
        return await self.redis.execute(
            "JSON.GET", f"{self.prefix}:guild:{guild_id}:members", f"{user_id}"
        )

    async def remove_member(self, guild_id, user_id):
        await self.redis.execute(
            "JSON.DEL", f"{self.prefix}:guild:{guild_id}:members", f"{user_id}"
        )

    async def iter_guild_members(self, guild_id):
        for key in await self.redis.execute(
            "JSON.OBJKEYS", f"{self.prefix}:guild:{guild_id}:members", "."
        ):
            yield orjson.loads(
                await self.redis.execute(
                    "JSON.GET", f"{self.prefix}:guild:{guild_id}:members", key
                )
            )
