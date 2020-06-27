import asyncio

from abc import ABC

from .broker import Broker
from .cache import EntityCache, NoEntityCache
from .entities import *
from .http import HTTPClient


class HTTPMixin(ABC):
    http: HTTPClient
    cache: EntityCache

    def _maybe_parse(self, data, klass):
        if data is not None:
            return klass(data, http=self.http, cache=self.cache)

        return data

    async def fetch_bot_user(self):
        result = await self.http.get_bot_user()
        return self._maybe_parse(result, User)

    async def fetch_user(self, user_id):
        result = await self.http.get_user(user_id)
        return self._maybe_parse(result, User)


class CacheMixin(ABC):
    http: HTTPClient
    cache: EntityCache

    def _maybe_parse(self, data, klass):
        if data is not None:
            return klass(data, http=self.http, cache=self.cache)

        return data

    async def get_guild(self, guild_id):
        result = await self.cache.get_guild(guild_id)
        return self._maybe_parse(result, Guild)

    async def get_channel(self, channel_id):
        result = await self.cache.get_channel(channel_id)
        return self._maybe_parse(result, Channel)

    async def get_role(self, role_id):
        result = await self.cache.get_role(role_id)
        return self._maybe_parse(result, Role)

    async def get_user(self, user_id):
        result = await self.cache.get_user(user_id)
        return self._maybe_parse(result, User)


class Client(HTTPMixin, CacheMixin):
    def __init__(
        self, broker: Broker, http: HTTPClient, cache: EntityCache = None, loop=None
    ):
        self.loop = loop or asyncio.get_event_loop()
        self.broker = broker
        broker.callback = self._event_received
        self.http = http
        self.cache = cache or NoEntityCache()

        self._listeners = {}

        self.user = None

    def add_listener(self, event, callback):
        event = event.upper()
        if event not in self._listeners:
            self._listeners[event] = [callback]

        else:
            self._listeners[event].append(callback)

    def listener(self, coro):
        event = coro.__name__.replace("on_", "")
        self.add_listener(event, coro)

        return coro

    def _process_listeners(self, event, *args):
        listeners = self._listeners.get(event)
        if listeners:
            for listener in listeners:
                self.loop.create_task(listener(*args))

    async def _event_received(self, event, data):
        parsers = {
            "MESSAGE_CREATE": Message.from_message_create,
            "MESSAGE_UPDATE": Message.from_message_update,
            "GUILD_CREATE": Guild.from_guild_create,
            "GUILD_UPDATE": Guild.from_guild_update
        }
        parser = parsers.get(event.upper())
        if parser:
            result = await parser(data=data, cache=self.cache, http=self.http)

        else:
            result = data

        if isinstance(result, (list, tuple)):
            self._process_listeners(event, *result)

        else:
            self._process_listeners(event, result)

    async def login(self):
        self.user = await self.fetch_bot_user()
