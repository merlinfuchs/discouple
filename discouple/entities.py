from abc import ABC
from datetime import datetime

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
    "Message",
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

    @staticmethod
    def requires_cache(func):
        def _wrapper(entity, *args, **kwargs):
            assert entity.has_cache(), "This method requires the cache to be present"
            return func(*args, **kwargs)

        return _wrapper

    @staticmethod
    def requires_http(func):
        def _wrapper(entity, *args, **kwargs):
            assert (
                entity.has_http()
            ), "This method requires the http client to be present"
            return func(*args, **kwargs)

        return _wrapper

    def _update(self, data):
        pass


class Guild(Entity):
    __slots__ = ("name",)

    def _update(self, data):
        self.name = data.get("name")

    @Entity.requires_http
    async def fetch_member(self, user_id):
        pass

    @Entity.requires_cache
    async def get_member(self, user_id):
        pass


class Channel(Entity):
    pass


class Role(Entity):
    pass


class User(Entity):
    pass


class Member(Entity):
    def __init__(self, data, *, cache=None, http=None):
        self.id = int(data["user"]["id"])
        self._cache = cache
        self._http = http
        self._update(data)


class Message(Entity):
    __slots__ = (
        "channel_id",
        "guild_id",
        "author",
        "content",
        "timestamp",
        "edited_timestamp",
        "tts",
        "mention_everyone",
        "mentions",
        "mention_role_ids",
        "mention_channels",
        "attachments",
        "embeds",
        "reactions",
        "nonce",
        "pinned",
        "webhook_id",
        "type",
        "activity",
        "application",
        "message_reference",
        "flags",
    )

    def _update(self, data):
        self.channel_id = int(data["channel_id"])
        self.guild_id = int(data["guild_id"]) if "guild_id" in data else None
        if "member" in data:
            data["member"]["user"] = data["author"]
            self.author = Member(data["member"])

        else:
            self.author = User(data["author"])

        self.content = data.get("content", "")
        self.timestamp = None
        self.edited_timestamp = None
        self.tts = data["tts"]
        self.mention_everyone = data["mention_everyone"]
        self.mentions = [User(m) for m in data["mentions"]]
        self.mention_role_ids = [int(r) for r in data["mention_roles"]]
        self.mention_channels = None
        self.attachments = None
        self.embeds = None
        self.reactions = None
        self.nonce = data.get("nonce")
        self.pinned = data["pinned"]
        self.webhook_id = data.get("webhook_id")
        self.type = None

        self.activity = None
        self.application = None
        self.message_reference = None

        self.flags = None

    @classmethod
    async def from_message_create(cls, data, *, cache=None, http=None):
        return cls(data, cache=cache, http=http)

    @classmethod
    async def from_message_update(cls, data, *, cache=None, http=None):
        return cls(data, cache=cache, http=http)
