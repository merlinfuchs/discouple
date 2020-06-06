from abc import ABC
import aio_pika
import ujson
import traceback
import asyncio


class Broker(ABC):
    def __init__(self, callback=None):
        async def _default_callback(*_, **__):
            pass

        self.callback = callback or _default_callback

    async def connect(self, group, *args, **kwargs):
        pass

    async def subscribe(self, queue, *events):
        pass

    async def send(self, data):
        pass


class AMQPBroker(Broker):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection = None
        self.channel = None
        self.exchange = None

    async def connect(self, group, *args, **kwargs):
        self.connection = await aio_pika.connect_robust(*args, **kwargs)
        self.channel = await self.connection.channel()
        self.exchange = await self.channel.declare_exchange(group, type="direct", durable=True)

    async def subscribe(self, queue, *events):
        queue = await self.channel.declare_queue(queue, auto_delete=not queue)
        for event in events:
            await queue.bind(self.exchange, event.upper())

        async with queue.iterator() as queue_iter:
            async for msg in queue_iter:
                try:
                    async with msg.process():
                        data = ujson.loads(msg.body)
                        await self.callback(msg.routing_key.upper(), data)

                except asyncio.CancelledError:
                    raise

                except Exception:
                    traceback.print_exc()

    async def send(self, data):
        await self.exchange.publish(
            aio_pika.Message(body=ujson.dumps(data).encode("utf-8")),
            routing_key="SEND"
        )
