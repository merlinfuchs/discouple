class Context:
    def __init__(self, bot, msg):
        self.bot = bot
        self.msg = msg

        self._data = {}

    def __getattr__(self, item):
        return getattr(self.msg, item)

    def add_data(self, name, data):
        self._data[name] = data

    def get_data(self, name):
        return self._data.get(name)

    async def resume_with(self, resume):
        """
        resume has a unique key, event and check
        put continues info and context into redis
        another worker receives the correct event and continues the command
        """
