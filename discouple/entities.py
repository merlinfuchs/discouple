from abc import ABC
from datetime import datetime

from .enums import *
from .flags import *

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


def maybe_int(v):
    return int(v) if v is not None else v


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

    def _maybe_parse(self, data, klass):
        if data is not None:
            return klass(data, http=self._http, cache=self._cache)

        return data

    @staticmethod
    def requires_cache(func):
        def _wrapper(entity, *args, **kwargs):
            assert entity.has_cache(), "This method requires the cache to be present"
            return func(entity, *args, **kwargs)

        return _wrapper

    @staticmethod
    def requires_http(func):
        def _wrapper(entity, *args, **kwargs):
            assert (
                entity.has_http()
            ), "This method requires the http client to be present"
            return func(entity, *args, **kwargs)

        return _wrapper

    def _update(self, data):
        pass


class Guild(Entity):
    __slots__ = (
        "name",
        "icon",
        "splash",
        "discovery_splash",
        "owner_id",
        "region",
        "afk_channel_id",
        "afk_timeout",
        "verification_level",
        "default_message_notifications",
        "explicit_content_filter",
        "roles",
        "emojis",
        "features",
        "mfa_level",
        "application_id",
        "widget_enabled",
        "widget_channel_id",
        "system_channel_id",
        "system_channel_flags",
        "rules_channel_id",
        "large",
        "unavailable",
        "member_count",
        "voice_states",
        "members",
        "channels",
        "presences",
        "max_presences",
        "max_members",
        "vanity_url_code",
        "description",
        "banner",
        "premium_tier",
        "premium_subscription_count",
        "preferred_locale",
        "public_updates_channel_id",
        "max_video_channel_users",
        "approximate_member_count",
        "approximate_presence_count"
    )

    def _update(self, data):
        self.name = data["name"]
        self.icon = data.get("icon")
        self.splash = data.get("splash")
        self.discovery_splash = data.get("discovery_splash")
        self.owner_id = int(data["owner_id"])
        self.region = data["region"]
        self.afk_channel_id = maybe_int(data["afk_channel_id"])
        self.afk_timeout = data["afk_timeout"]
        self.verification_level = GuildVerificationLevel(data["verification_level"])
        self.default_message_notifications = GuildMessageNotificationLevel(data["default_message_notifications"])
        self.explicit_content_filter = GuildContentFilterLevel(data["explicit_content_filter"])
        self.roles = [Role(r) for r in data["roles"]]
        self.emojis = None
        self.features = data["features"]
        self.mfa_level = MFALevel(data["mfa_level"])
        self.application_id = maybe_int(data["application_id"])
        self.widget_enabled = data.get("widget_enabled", False)
        self.widget_channel_id = maybe_int(data.get("widget_channel_id"))
        self.system_channel_id = maybe_int(data["system_channel_id"])
        self.system_channel_flags = SystemChannelFlags(data["system_channel_flags"])
        self.rules_channel_id = maybe_int(data["rules_channel_id"])
        self.large = data.get("large", False)
        self.unavailable = data.get("unavailable", False)
        self.member_count = data.get("member_count")
        self.voice_states = None
        self.members = [Member(m) for m in data.get("members", [])]
        self.channels = [Channel(c) for c in data.get("channels", [])]
        self.presences = None
        self.max_presences = data.get("max_presences", 25000)
        self.max_members = data.get("max_members")
        self.vanity_url_code = data.get("vanity_url_code")
        self.description = data.get("description")
        self.banner = data.get("banner")
        self.premium_tier = GuildPremiumTier(data["premium_tier"])
        self.premium_subscription_count = data.get("premium_subscription_count", 0)
        self.preferred_locale = data["preferred_locale"]
        self.public_updates_channel_id = maybe_int(data["public_updates_channel_id"])
        self.max_video_channel_users = data.get("max_video_channel_users")
        self.approximate_member_count = data.get("approximate_member_count")
        self.approximate_presence_count = data.get("approximate_presence_count")

    @classmethod
    async def from_guild_create(cls, data, *, cache=None, http=None):
        await cache.store_guild(data)
        return cls(data, cache=cache, http=http)

    @classmethod
    async def from_guild_update(cls, data, *, cache=None, http=None):
        await cache.store_guild(data)
        return cls(data, cache=cache, http=http)

    @Entity.requires_http
    async def fetch_member(self, user_id):
        pass

    @Entity.requires_cache
    async def get_member(self, user_id):
        pass


class Channel(Entity):
    def _update(self, data):
        self.name = data["name"]


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

    @Entity.requires_http
    async def send(self, *args, **kwargs):
        result = await self._http.create_message(self.channel_id, *args, **kwargs)
        return self._maybe_parse(result, Message)

    @Entity.requires_cache
    async def get_channel(self):
        result = await self._cache.get_channel(self.channel_id)
        return self._maybe_parse(result, Channel)

    @Entity.requires_http
    async def fetch_channel(self):
        result = await self._http.get_channel(self.channel_id)
        return self._maybe_parse(result, Channel)

    @Entity.requires_cache
    async def get_guild(self):
        result = await self._cache.get_guild(self.guild_id)
        return self._maybe_parse(result, Guild)

    @Entity.requires_http
    async def fetch_guild(self):
        result = await self._http.get_guild(self.guild_id)
        return self._maybe_parse(result, Guild)

    def reply(self, *args, **kwargs):
        return self.send(*args, **kwargs)
