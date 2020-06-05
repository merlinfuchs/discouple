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
        if event not in self._listeners:
            self._listeners[event] = [callback]

        else:
            self._listeners[event].append(callback)

    def _process_listeners(self, event, *args):
        listeners = self._listeners.get(event)
        if listeners:
            for listener in listeners:
                self.loop.create_task(listener(event, *args))

    async def _event_received(self, event, data):
        # parse data to entitiy

        self._process_listeners(event, data)

    async def login(self):
        self.user = await self.fetch_bot_user()
