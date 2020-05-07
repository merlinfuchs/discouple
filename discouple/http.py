import asyncio
import dataclasses
import aiohttp
import time
import math
import ujson
from urllib.parse import quote as urlquote
from datetime import datetime, timezone
import sys


__all__ = (
    'Route',
    'QueuedRequest',
    'RateLimitHandler',
    'HTTPClient'
)


@dataclasses.dataclass
class Route:
    """
    Represents a discord api route with all major and minor parameters
    """
    BASE = 'https://discordapp.com/api/v7'

    path: str
    method: str = "GET"
    parameters: dict = dataclasses.field(default_factory=dict)

    @property
    def url(self) -> str:
        return self.BASE + self.path.format(**self.parameters)

    @property
    def default_bucket(self) -> str:
        """
        Used when the X-RateLimit-Bucket was not returned
        """
        if "webhook_id" in self.parameters:
            return "{0.path}_{webhook_id}".format(self, **self.parameters)

        return "{0.path}_{guild_id}_{channel_id}".format(self, **self.parameters)


@dataclasses.dataclass
class QueuedRequest:
    """
    Represents a request including route and http parameters
    It also includes attributes for efficient queueing
    """
    future: asyncio.Future

    route: Route
    options: dict

    time_added: float = dataclasses.field(default_factory=time.perf_counter)
    ttl: int = 30
    tries: int = 0

    @property
    def expiration(self) -> float:
        if self.ttl is not None:
            return self.time_added + self.ttl

        return math.inf

    def __await__(self):
        return self.future


class RateLimitHandler:
    """
    Responsible for mapping the ratelimits to the correct routes
    Everything is async to support distributed handling in subclasses
    """
    def __init__(self):
        self._global = 0
        self._buckets = {}
        self._deltas = {}

    async def get_bucket(self, route: Route) -> str:
        return self._buckets.get(route.path, route.default_bucket)

    async def get_delta(self, route: Route) -> float:
        global_delta = self._global - time.perf_counter()
        if global_delta > 0:
            return global_delta

        bucket = await self.get_bucket(route)
        return self._deltas.get(bucket, 0)

    async def set_delta(self, route: Route, delta: float):
        bucket = await self.get_bucket(route)
        self._deltas[bucket] = delta

    async def set_global(self, delta):
        self._global = time.perf_counter() + delta

    async def set_bucket(self, route: Route, bucket):
        self._buckets[route.path] = bucket


async def json_or_text(response):
    text = await response.text(encoding='utf-8')
    try:
        if response.headers['content-type'] == 'application/json':
            return ujson.loads(text)
    except KeyError:
        # Thanks Cloudflare
        pass

    return text


class HTTPClient:
    """
    Interacts with the discord rest api and handles the rate limits
    A request queue is used internally to help reduce 429s
    """
    def __init__(self, loop, session, token, ratelimit_handler=None):
        self.loop = loop or asyncio.get_event_loop()
        self.session = session
        self.token = token
        self.queue = asyncio.Queue()

        self._worker = None
        self._ratelimits = ratelimit_handler or RateLimitHandler()

        user_agent = 'DisCouple (https://github.com/Merlintor/discouple) Python/{1[0]}.{1[1]} aiohttp/{2}'
        self.user_agent = user_agent.format(sys.version_info, aiohttp.__version__)

    async def request(self, route, ttl=30, **options):
        """
        Add a route to the request queue
        """
        self.start_worker()

        future = self.loop.create_future()
        req = QueuedRequest(future=future, route=route, ttl=ttl, options=options)
        await self.queue.put(req)
        return await req

    def start_worker(self):
        if self._worker is None or self._worker.done():
            self._worker = self.loop.create_task(self._request_worker())

    async def _perform_request(self, req: QueuedRequest):
        def _put_back(_delta):
            """
            Put request back into the queue after delta seconds
            Resets the request expiration
            """
            req.time_added = time.perf_counter()
            return self.loop.call_later(_delta, self.queue.put, req)

        req.tries += 1
        route = req.route
        delta = await self._ratelimits.get_delta(route)
        if delta > 0:
            return _put_back(delta)

        options = req.options
        options["headers"] = headers = {
            'User-Agent': self.user_agent,
            'X-Ratelimit-Precision': 'millisecond',
            'Authorization': 'Bot ' + self.token
        }

        if "json" in options:
            headers["Content-Type"] = "application/json"
            options["data"] = ujson.dumps(options.pop("json"))

        if "reason" in options:
            headers["X-Audit-Log-Reason"] = urlquote(options.pop("reason"), safe="/ ")

        async with self.session.request(
            method=route.method,
            url=route.url,
            raise_for_status=False,
            **options
        ) as resp:
            data = await json_or_text(resp)

            rl_bucket = resp.headers.get('X-Ratelimit-Remaining')
            if rl_bucket is not None:
                await self._ratelimits.set_bucket(route, rl_bucket)

            rl_remaining = resp.headers.get('X-Ratelimit-Remaining')
            if rl_remaining == 0:
                reset = datetime.fromtimestamp(resp.headers["X-Ratelimit-Reset"], timezone.utc)
                delta = (reset - datetime.utcnow()).total_seconds()
                await self._ratelimits.set_delta(route, delta)

            if 300 > resp.status >= 200:
                return req.future.set_result(data)

            if resp.status == 429 and resp.headers.get('Via'):
                retry_after = data['retry_after'] / 1000.0
                is_global = data.get('global', False)
                if is_global:
                    await self._ratelimits.set_global(retry_after)

                else:
                    await self._ratelimits.set_delta(route, retry_after)

                return _put_back(retry_after)

            if resp.status in {500, 502} and req.tries <= 5:
                return _put_back(req.tries * 2)

            resp.raise_for_status()

    async def _request_worker(self):
        while True:
            req = await self.queue.get()
            try:
                if req.expiration < time.perf_counter():
                    req.future.set_exception(asyncio.TimeoutError())
                    continue

                await self._perform_request(req)

            except asyncio.CancelledError:
                raise

            except Exception as e:
                req.future.set_exception(e)

            finally:
                self.queue.task_done()



