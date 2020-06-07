class Context:
    async def resume_with(self, resume):
        """
        resume has a unique key, event and check
        put continues info and context into redis
        another worker receives the correct event and continues the command
        """
