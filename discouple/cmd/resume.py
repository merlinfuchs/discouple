from abc import ABC


class BaseResumeHandler(ABC):
    pass


class Resumable(ABC):
    def __init__(self):
        self.resumes = set()

    def resume(self, *args, **kwargs):
        """
        Used to replace wait_for to wait for an event during a command
        Commands are split up into sections which should be decorated with this
        Each section can be run from another worker without state
        """

        def _predicate(callback):
            res = Resume(self, callback, *args, **kwargs)
            self.resumes.add(res)
            return res

        return _predicate


class Resume(Resumable):
    def __init__(self, parent, callback, event, check):
        super().__init__()
        self.parent = parent
        self.callback = callback
        self.event = event
        self.check = check

        self.module = None

    @property
    def full_name(self):
        return (self.parent.full_name + " " + self.event).strip()

    def fill_module(self, module):
        self.module = module
        for resume in self.resumes:
            resume.fill_module(module)

    async def execute(self, *args, **kwargs):
        if self.module is None:
            await self.callback(*args, **kwargs)

        else:
            await self.callback(self.module, *args, **kwargs)
