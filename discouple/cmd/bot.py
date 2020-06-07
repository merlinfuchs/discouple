from ..client import Client
from .command import CommandTable


class Bot(Client, CommandTable):
    def __init__(self, prefix=None, resume_handler=None, *args, **kwargs):
        self.prefix = prefix
        self.resume_handler = resume_handler or None
        super().__init__(*args, **kwargs)
