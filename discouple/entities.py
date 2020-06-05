from datetime import datetime
from abc import ABC

DISCORD_EPOCH = 1420070400000


class Hashable(ABC):
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


class Snowflake:
    __slots__ = ("id",)

    def __init__(self, id):
        self.id = id

    def __hash__(self):
        return int(self.id) >> 22

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.id == self.id

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return other.id != self.id

        return True

    @property
    def created_at(self):
        return datetime.utcfromtimestamp(((int(self.id) >> 22) + DISCORD_EPOCH) / 1000)


class Guild(Hashable):
    __slots__ = ("id", "name")

    def __init__(self, *, data, cache):
        self._cache = cache

        self.id = int(data["id"])
        self.name = data.get("name")


class Channel(Hashable):
    def __init__(self, *, data, cache):
        self._cache = cache


class Role(Hashable):
    def __init__(self, *, data, cache):
        self._cache = cache


class User(Hashable):
    def __init__(self, *, data, cache):
        self._cache = cache


class Member(Hashable):
    def __init__(self, *, data, cache):
        self._cache = cache


class Message(Hashable):
    def __init__(self, *, data, cache):
        self._cache = cache
