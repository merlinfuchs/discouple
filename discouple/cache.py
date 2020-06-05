from abc import ABC


__all__ = (
    'EntityCache',
    'NoEntityCache',
    'LocalEntityCache',
    'RedisEntityCache'
)


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


class RedisEntityCache(EntityCache):
    pass
