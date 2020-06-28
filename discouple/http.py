import asyncio
import dataclasses
import math
import sys
import time

from abc import ABC
from datetime import datetime, timezone
from urllib.parse import quote as urlquote

import aiohttp
import orjson

__all__ = (
    "Route",
    "QueuedRequest",
    "BaseRateLimitHandler",
    "LocalRateLimitHandler",
    "RedisRateLimitHandler",
    "HTTPClient",
)


class Route:
    """
    Represents a discord api route with all major and minor parameters
    """

    BASE = "https://discord.com/api/v7"

    def __init__(self, method: str, path: str, **parameters):
        self.method = method
        self.path = path
        self.parameters = {"guild_id": None, "channel_id": None, "webhook_id": None}
        self.parameters.update(parameters)

    @property
    def url(self) -> str:
        return f"{self.BASE}{self.path.format(**self.parameters)}"

    @property
    def default_bucket(self) -> str:
        """
        Used when the X-RateLimit-Bucket was not returned
        """
        webhook_id = self.parameters.get("webhook_id")
        if webhook_id is not None:
            return f"{self.path}_{webhook_id}"

        return (
            "{self.path}_{self.parameters['guild_id']}_{self.parameters['channel_id']}"
        )


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
    timeout: int = 30
    tries: int = 0

    @property
    def expiration(self) -> float:
        if self.timeout is not None:
            return self.time_added + self.timeout

        return math.inf

    def __await__(self):
        return self.future.__await__()


class BaseRateLimitHandler(ABC):
    """
    Responsible for mapping the ratelimits to the correct routes
    Everything is async to support distributed handling in subclasses
    """

    async def get_bucket(self, route: Route) -> str:
        pass

    async def get_delta(self, route: Route) -> float:
        pass

    async def set_delta(self, route: Route, delta: float):
        pass

    async def set_global(self, delta: float):
        pass

    async def set_bucket(self, route: Route, bucket: str):
        pass


class LocalRateLimitHandler(BaseRateLimitHandler):
    """
    Handles ratelimits locally without being aware of possible distribution
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

    async def set_global(self, delta: float):
        self._global = time.perf_counter() + delta

    async def set_bucket(self, route: Route, bucket: str):
        self._buckets[route.path] = bucket


class RedisRateLimitHandler(BaseRateLimitHandler):
    """
    Handles ratelimits in redis using key expiration
    """

    def __init__(self, redis, key_prefix="ratelimit:"):
        self._redis = redis
        self._key_prefix = key_prefix

    async def get_bucket(self, route: Route) -> str:
        bucket = await self._redis.hget(f"{self._key_prefix}buckets", route.path)
        if bucket:
            bucket = bucket.decode("utf-8")
        return bucket or route.default_bucket

    async def get_delta(self, route: Route) -> float:
        global_delta = await self._redis.ttl(f"{self._key_prefix}global")
        if global_delta > 0:
            return global_delta

        bucket = await self.get_bucket(route)
        delta = await self._redis.ttl(f"{self._key_prefix}{bucket}")
        return min(delta, 0)

    async def set_delta(self, route: Route, delta: float):
        bucket = await self.get_bucket(route)
        await self._redis.setex(f"{self._key_prefix}{bucket}", delta, 1)

    async def set_global(self, delta: float):
        return await self._redis.setex(f"{self._key_prefix}global", delta, 1)

    async def set_bucket(self, route: Route, bucket: str):
        return await self._redis.hset(f"{self._key_prefix}buckets", route.path, bucket)


async def json_or_text(response):
    try:
        if response.headers["content-type"] == "application/json":
            # orjson prefers bytes
            body = await response.read()
            return orjson.loads(body)
    except KeyError:
        # Thanks Cloudflare
        pass

    return await response.text(encoding="utf-8")


class HTTPClient:
    """
    Interacts with the discord rest api and handles the rate limits
    A request queue is used internally to help reduce 429s
    """

    def __init__(self, session, token, loop=None, ratelimit_handler=None):
        self.loop = loop or asyncio.get_event_loop()
        self.session = session
        self.token = token
        self.queue = asyncio.Queue()

        self._worker = None
        self._ratelimits = ratelimit_handler or LocalRateLimitHandler()

        user_agent = (
            "DisCouple (https://github.com/Merlintor/discouple) Python/{1[0]}"
            " aiohttp/{1}"
        )
        self.user_agent = user_agent.format(sys.version_info, aiohttp.__version__)

    async def request(self, route, timeout=None, **options):
        """
        Add a route to the request queue
        """
        self.start_worker()

        future = self.loop.create_future()
        req = QueuedRequest(
            future=future, route=route, timeout=timeout, options=options
        )
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
            return self.loop.call_later(_delta, self.queue.put_nowait, req)

        req.tries += 1
        route = req.route
        delta = await self._ratelimits.get_delta(route)
        if delta > 0:
            return _put_back(delta)

        options = req.options
        options["headers"] = headers = {
            "User-Agent": self.user_agent,
            "X-Ratelimit-Precision": "millisecond",
            "Authorization": f"Bot {self.token}",
        }

        if "json" in options:
            headers["Content-Type"] = "application/json"
            options["data"] = orjson.dumps(options.pop("json")).decode("utf-8")

        if "reason" in options:
            headers["X-Audit-Log-Reason"] = urlquote(options.pop("reason"), safe="/ ")

        async with self.session.request(
            method=route.method, url=route.url, raise_for_status=False, **options
        ) as resp:
            data = await json_or_text(resp)

            rl_bucket = resp.headers.get("X-Ratelimit-Remaining")
            if rl_bucket is not None:
                await self._ratelimits.set_bucket(route, rl_bucket)

            rl_remaining = resp.headers.get("X-Ratelimit-Remaining")
            if rl_remaining == 0:
                reset = datetime.fromtimestamp(
                    resp.headers["X-Ratelimit-Reset"], timezone.utc
                )
                delta = (reset - datetime.utcnow()).total_seconds()
                await self._ratelimits.set_delta(route, delta)

            if 300 > resp.status >= 200:
                return req.future.set_result(data)

            if resp.status == 429 and resp.headers.get("Via"):
                retry_after = data["retry_after"] / 1000.0
                is_global = data.get("global", False)
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

    # ---- Specific Route Implementations ---

    def create_message(self, channel_id, content):
        return self.request(
            Route("POST", "/channels/{channel_id}/messages", channel_id=channel_id),
            json={"content": content},
        )

    def get_bot_user(self):
        return self.request(Route("GET", "/users/@me"))

    def get_user(self, user_id):
        return self.request(Route("GET", "/users/{user_id}", user_id=user_id))

    def get_channel(self, channel_id):
        return self.request(
            Route("GET", "/channels/{channel_id}", channel_id=channel_id)
        )

    def get_guild(self, guild_id):
        return self.request(Route("GET", "/guilds/{guild_id}", guild_id=guild_id))
