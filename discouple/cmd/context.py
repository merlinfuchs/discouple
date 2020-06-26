class Context:
    def __init__(self, bot, msg):
        self.bot = bot
        self.msg = msg

    def send(self, *args, **kwargs):
        return self.msg.send(*args, **kwargs)

    def reply(self, *args, **kwargs):
        return self.send(*args, **kwargs)

    async def resume_with(self, resume):
        """
        resume has a unique key, event and check
        put continues info and context into redis
        another worker receives the correct event and continues the command
        """
