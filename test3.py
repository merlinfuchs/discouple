import asyncio
import aiohttp
from discouple import Client, LocalRateLimitHandler, HTTPClient, AMQPBroker, LocalEntityCache


async def run():
    cache = LocalEntityCache()
    broker = AMQPBroker()
    await broker.connect("gateway")

    limiter = LocalRateLimitHandler()
    http = HTTPClient(
        ratelimit_handler=limiter,
        session=aiohttp.ClientSession(),
        token=""
    )

    client = Client(broker=broker, http=http, cache=cache)

    @client.listener
    async def on_message_create(msg):
        print(msg.content)

    await client.login()
    await broker.subscribe("asda", "MESSAGE_CREATE")


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
