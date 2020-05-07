import aiohttp
import asyncio
import ujson
import logging
import zlib
import threading
import time
import concurrent.futures
from enum import IntEnum


log = logging.getLogger(__name__)


__all__ = (
    'DiscordWebSocket',
    'HeartbeatHandler',
    'ResumeWebSocket',
    'IdentifyWebSocket',
    'IdentifyLock',
    'Opcodes'
)


class ResumeWebSocket(Exception):
    pass


class IdentifyWebSocket(Exception):
    pass


class Opcodes(IntEnum):
    DISPATCH = 0
    HEARTBEAT = 1
    IDENTIFY = 2
    PRESENCE = 3
    VOICE_STATE = 4
    VOICE_PING = 5
    RESUME = 6
    RECONNECT = 7
    REQUEST_MEMBERS = 8
    INVALIDATE_SESSION = 9
    HELLO = 10
    HEARTBEAT_ACK = 11
    GUILD_SYNC = 12


class IdentifyLock:
    """
    Wraps around asyncio.Lock and provides a context manager
    Both acquire and release are async to support distributed locks in subclasses
    """

    def __init__(self):
        self._lock = asyncio.Lock()

    async def acquire(self):
        await self._lock.acquire()

    async def release(self):
        self._lock.release()

    async def __aenter__(self):
        return await self.acquire()

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return await self.release()


class HeartbeatHandler(threading.Thread):
    def __init__(self, dws, interval, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.dws = dws
        self.interval = interval
        self.timeout = 60

        self.daemon = True

        self._stop = threading.Event()
        self._last_ack = time.perf_counter()
        self._last_send = time.perf_counter()
        self.latency = -1

    def run(self):
        while not self._stop.wait(self.interval):
            if self._last_ack + self.timeout < time.perf_counter():
                print("latency over", self.latency)

            f = asyncio.run_coroutine_threadsafe(self.dws.send_heartbeat(), self.dws.loop)
            try:
                total_time = 0
                while True:
                    try:
                        f.result(5)
                        break

                    except concurrent.futures.TimeoutError:
                        total_time += 5
                        print("blocked for", total_time)

            except Exception:
                self.stop()

            else:
                self._last_send = time.perf_counter()

    def stop(self):
        self._stop.set()

    def ack(self):
        self._last_ack = ack_time = time.perf_counter()
        self.latency = ack_time - self._last_send
        log.debug(f"Heartbeat was acknowledged with a latency of "
                  f"{int(self.latency * 1000)}ms on shard {self.dws.shard_id}")
        if self.latency > 10:
            pass


class DiscordWebSocket:
    def __init__(self, session: aiohttp.ClientSession, *, dispatch, loop=None, **options):
        self._session = session
        self.loop = loop or asyncio.get_event_loop()
        self._dispatch = dispatch
        self._identify_lock = options.get("identify_lock") or IdentifyLock()

        self.token = options.get("token")
        self.shard_id = options.get("shard_id", 0)
        self.shard_count = options.get("shard_count", 1)

        self._session_id = options.get("session_id")
        self._last_seq = options.get("seq")

        self._ws = None
        self._hb_handler = None
        self._gateway = None

        # Decompression
        self._buffer = bytearray()
        self._zlip = options.get("zlib", zlib.decompressobj())

    async def _message_received(self, msg):
        try:
            op = Opcodes(msg.get("op"))
        except ValueError:
            log.warning(f"Received unknown opcode {msg.get('op')} on shard {self.shard_id}")
            return

        data = msg.get("d")
        seq = msg.get("s")
        if seq is not None:
            self._last_seq = seq

        if op != Opcodes.DISPATCH:
            log.debug(f"Received op {op.name} ({op.value}) on shard {self.shard_id}")
            if op == Opcodes.HEARTBEAT_ACK:
                self._hb_handler.ack()

            elif op == Opcodes.HEARTBEAT:
                # The gateway requests a heartbeat from us
                await self.send_heartbeat()

            elif op == Opcodes.RECONNECT:
                raise ResumeWebSocket()

            elif op == Opcodes.INVALIDATE_SESSION:
                if data is True:
                    raise ResumeWebSocket()

                raise IdentifyWebSocket()

            elif op == Opcodes.HELLO:
                interval = data['heartbeat_interval'] / 1000.0
                if self._hb_handler is not None:
                    self._hb_handler.stop()

                self._hb_handler = HeartbeatHandler(
                    dws=self,
                    interval=interval
                )
                await self.send_heartbeat()
                self._hb_handler.start()

            return

        event = msg.get("t")

        if event == "READY":
            self._session_id = data["session_id"]

        self._dispatch(event, data)

    def is_resumable(self):
        """
        Some error codes are considered "resumable" and some aren't
        """
        return self._ws.close_code not in (1000, 4004, 4010, 4011)

    async def poll_message(self):
        msg = await self._ws.receive()

        if msg.type != aiohttp.WSMsgType.TEXT and msg.type != aiohttp.WSMsgType.BINARY:
            if msg.type == aiohttp.WSMsgType.CLOSE:
                log.warning(f"Websocket of shard {self.shard_id} was closed {self._ws.close_code} ({msg.extra})")
                if self.is_resumable():
                    raise ResumeWebSocket()

                raise IdentifyWebSocket()

            elif msg.type == aiohttp.WSMsgType.ERROR:
                print("poll error", msg)

            return

        data = msg.data
        # Decompress using zlib
        if type(data) is bytes:
            zlib_suffix = b'\x00\x00\xff\xff'
            self._buffer.extend(data)
            if len(data) >= 4 and data[-len(zlib_suffix):] == zlib_suffix:
                data = self._zlip.decompress(self._buffer).decode("utf-8")
                self._buffer = bytearray()

            else:
                return

        await self._message_received(ujson.loads(data))

    async def start_polling(self):
        while not self._ws.closed:
            try:
                await self.poll_message()

            except ResumeWebSocket:
                log.info(f"Resuming websocket of shard {self.shard_id}")
                if not self._ws.closed:
                    await self.close()

                await self.connect()
                await self.resume()

            except IdentifyWebSocket:
                log.info(f"Re-Identifying websocket of shard {self.shard_id}")
                self._last_seq = None
                self._session_id = None
                if self._ws.closed:
                    await self.connect()

                await self.identify()

    async def send_op(self, op, data):
        log.debug(f"Sending op {op.name} ({op.value}) on shard {self.shard_id}")
        await self._ws.send_json({
            "op": op,
            "d": data
        })

    def send_heartbeat(self):
        return self.send_op(
            op=Opcodes.HEARTBEAT,
            data=self._last_seq
        )

    async def identify(self):
        async with self._identify_lock:
            await asyncio.sleep(5)
            await self.send_op(
                op=Opcodes.IDENTIFY,
                data={
                    "token": self.token,
                    "properties": {},
                    "shard": [self.shard_id, self.shard_count],
                    # TODO: Fix decompression
                    "compress": False
                }
            )

    async def resume(self):
        await self.send_op(
            op=Opcodes.RESUME,
            data={
                "token": self.token,
                "seq": self._last_seq,
                "session_id": self._session_id
            }
        )

    async def request_guild_members(self, guild_id, timeout=30, **options):
        pass

    async def update_voice_state(self):
        pass

    async def set_presence(self):
        pass

    def close(self, code=4000):
        if self._hb_handler is not None:
            self._hb_handler.stop()

        return self._ws.close(code=code)

    async def connect(self, gateway=None):
        self._gateway = gateway or self._gateway
        self._ws = await self._session.ws_connect(
            url=self._gateway.url,
            max_msg_size=0
        )
        await self.poll_message()
