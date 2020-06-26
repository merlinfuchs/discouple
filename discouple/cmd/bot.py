from ..client import Client
from .command import CommandTable, Command
from .errors import *
from .context import Context


class Bot(Client, CommandTable):
    def __init__(self, prefix, resume_handler=None, *args, **kwargs):
        self.prefix = prefix
        self.resume_handler = resume_handler or None
        self.modules = []
        Client.__init__(self, *args, **kwargs)
        CommandTable.__init__(self)
        self.add_listener("MESSAGE_CREATE", self.process_command)

    def add_module(self, module):
        self.modules.append(module)
        for cmd in module.commands:
            cmd.fill_module(module)
            self.commands.append(cmd)

        for listener in module.listeners:
            listener.module = module
            self.add_listener(listener.name, listener.execute)

        for task in module.tasks:
            task.module = module
            self.loop.create_task(task.construct())

    async def process_command(self, msg):
        if not msg.content.startswith(self.prefix):
            return

        parts = msg.content[len(self.prefix):].split(" ")
        remaining, cmd = self.find_command(parts)
        if not isinstance(cmd, Command):
            return

        ctx = Context(self, msg)
        await cmd.execute(ctx, remaining)
