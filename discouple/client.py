import asyncio
from abc import ABC

from .broker import Broker
from .http import HTTPClient
from .cache import EntityCache, NoEntityCache
from .entities import *


class HTTPMixin(ABC):
    http: HTTPClient
    cache: EntityCache

    async def _fetch_and_parse(self, coro, klass):
        data = await coro
        return klass(data=data, cache=self.cache)

    def fetch_bot_user(self):
        return self._fetch_and_parse(self.http.get_bot_user(), klass=User)

    def fetch_user(self, user_id):
        return self._fetch_and_parse(self.http.get_user(user_id), klass=User)


class CacheMixin(ABC):
    cache: EntityCache

    async def _get_and_parse(self, coro, klass):
        data = await coro
        return klass(data=data, cache=self.cache)

    def get_guild(self, guild_id):
        return self._get_and_parse(self.cache.get_guild(guild_id), klass=Guild)

    def get_channel(self, channel_id):
        return self._get_and_parse(self.cache.get_channel(channel_id), klass=Channel)

    def get_role(self, role_id):
        return self._get_and_parse(self.cache.get_role(role_id), klass=Role)

    def get_user(self, user_id):
        return self._get_and_parse(self.cache.get_user(user_id), klass=User)


class Client(HTTPMixin, CacheMixin):
    def __init__(self, broker: Broker, http: HTTPClient, cache: EntityCache = None, loop=None):
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
            "MESSAGE_CREATE": Message.from_message_create
        }
        parser = parsers.get(event.upper())
        result = await parser(data=data, cache=self.cache, http=self.http)

        if isinstance(result, (list, tuple)):
            self._process_listeners(event, *result)

        else:
            self._process_listeners(event, result)

    async def login(self):
        self.user = await self.fetch_bot_user()
