from datetime import datetime
from abc import ABC

DISCORD_EPOCH = 1420070400000


__all__ = (
    "Hashable",
    "Snowflake",
    "Entity",
    "Guild",
    "Channel",
    "Role",
    "User",
    "Member",
    "Message"
)


class Hashable(ABC):
    id: int

    __slots__ = ("id",)

    def __hash__(self):
        return self.id >> 22

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.id == self.id

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return other.id != self.id

        return True

    @property
    def created_at(self):
        return datetime.utcfromtimestamp(((self.id >> 22) + DISCORD_EPOCH) / 1000)


class Snowflake(Hashable):
    def __init__(self, id):
        self.id = id


class Entity(Hashable):
    __slots__ = ("id", "_cache", "_http")

    def __init__(self, data, *, cache=None, http=None):
        self.id = int(data["id"])
        self._cache = cache
        self._http = http
        self._update(data)

    def has_cache(self):
        return self._cache is not None

    def has_http(self):
        return self._http is not None

    def _update(self, data):
        pass


class Guild(Entity):
    __slots__ = ("name",)

    def _update(self, data):
        self.name = data.get("name")


class Channel(Entity):
    pass


class Role(Entity):
    pass


class User(Entity):
    pass


class Member(Entity):
    pass


class Message(Entity):
    __slots__ = ("content",)

    def _update(self, data):
        self.content = data.get("content", "")

    @classmethod
    async def from_message_create(cls, data, *, cache=None, http=None):
        return cls(data, cache=cache, http=http)
