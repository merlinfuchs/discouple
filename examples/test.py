import asyncio
import logging
import traceback

import aiohttp

from discouple import *

logging.basicConfig(level=logging.DEBUG)


class DummyGateway:
    url = "wss://gateway.discord.gg/?v=6&encoding=json%compress=zlib-stream"


async def test():
    def dummy_dispatch(event, data):
        pass
        # print("dispatch", event)

    session = aiohttp.ClientSession()
    test = DiscordGateway(
        session=session, dispatch=dummy_dispatch, shard_count=5, token=""
    )

    async def command_test():
        await asyncio.sleep(10)

    test.loop.create_task(command_test())
    await test.connect(DummyGateway())
    loop.create_task(test.identify())
    try:
        await test.keep_polling()
    except Exception:
        traceback.print_exc()
        raise


loop = asyncio.get_event_loop()
loop.run_until_complete(test())
