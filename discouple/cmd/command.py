import inspect

from abc import ABC

from .check import Check, Cooldown
from .errors import *
from .resume import Resumable, Resume


class CommandTable(ABC):
    def __init__(self, *commands, parent_checks=True):
        self.parent = None  # Gets filled later
        self._checks = set()
        self._cooldown = None
        self.commands = list(commands)
        self.parent_checks = parent_checks

    @property
    def checks(self):
        if self.parent is not None and self.parent_checks:
            yield from self.parent.checks

        yield from self._checks

    @property
    def full_name(self):
        return ""

    def set_cooldown(self, cooldown):
        self._cooldown = cooldown

    async def reset_cooldown(self):
        pass

    def add_check(self, check):
        self._checks.add(check)

    def remove_check(self, check):
        self._checks.remove(check)

    def command(self, *args, **kwargs):
        def _predicate(callback):
            cmd = Command(callback, *args, **kwargs)
            self.commands.append(cmd)
            return cmd

        return _predicate

    def filter_commands(self, parts):
        if len(parts) == 0:
            return []

        for command in self.commands:
            if isinstance(command, Command):
                if command.name == parts[0] or parts[0] in command.aliases:
                    yield command

            else:
                yield command

    def find_command(self, parts):
        for cmd in self.filter_commands(parts):
            try:
                parts, res = cmd.find_command(parts[1:])
            except ValueError:
                continue

            else:
                return parts, res

        return parts, self


class CommandParameter:
    def __init__(self, name, kind, default=inspect.Parameter.empty, converter=None):
        self.name = name
        self.kind = kind
        self.default = default
        if self.default == inspect.Parameter.empty:
            if self.kind == inspect.Parameter.KEYWORD_ONLY:
                self.default = ""

            elif self.kind == inspect.Parameter.VAR_POSITIONAL:
                self.default = tuple()

        self.converter = converter
        if converter is bool:
            def _bool_converter(a):
                a = str(a).lower()
                return a == "y" or a == "yes" or a == "true"

            self.converter = _bool_converter

    @classmethod
    def from_parameter(cls, p):
        return cls(
            p.name,
            p.kind,
            p.default,
            p.annotation if p.annotation != inspect.Parameter.empty else None,
        )

    def parse(self, args):
        if len(args) == 0:
            if self.default != inspect.Parameter.empty:
                return self.default

            raise NotEnoughArguments(self)

        if self.kind == inspect.Parameter.VAR_POSITIONAL:
            converter = self.converter or tuple
            arg = tuple(args)
            args.clear()

        elif self.kind == inspect.Parameter.KEYWORD_ONLY:
            converter = self.converter or str
            arg = " ".join(args)
            args.clear()

        elif self.kind == inspect.Parameter.VAR_KEYWORD:
            converter = self.converter or dict
            arg = {a: b for a, b in map(lambda ab: ab.split("="), args)}
            args.clear()

        else:
            converter = self.converter or str
            arg = args.pop(0)

        if False:  # issubclass(converter, Converter):
            return converter(self, arg)

        else:
            try:
                return converter(arg)
            except Exception as e:
                raise ConverterFailed(self, arg, str(e))


class Command(CommandTable, Resumable):
    def __init__(
            self,
            callback,
            name=None,
            description=None,
            aliases=None,
            hidden=None,
            *args,
            **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.module = None  # Gets filled later if this command belongs to a module

        self.resumes = []

        cb = callback
        while isinstance(cb, Check):
            if isinstance(cb, Cooldown):
                self.set_cooldown(cb)

            else:
                self.add_check(cb)

            cb = cb.next

        self.callback = cb
        self.name = name or self.callback.__name__

        doc = inspect.getdoc(self.callback)
        self.description = description or inspect.cleandoc(doc) if doc else ""
        self.aliases = aliases or []
        self.hidden = hidden

        sig = inspect.signature(self.callback)
        self.parameters = [
            CommandParameter.from_parameter(p)
            for _, p in list(sig.parameters.items())
            if p.name != "self" and p.name != "ctx"  # Skip self and ctx
        ]

    @property
    def brief(self):
        lines = self.description.splitlines()
        if len(lines) == 0:
            return ""

        line = lines[0]
        if len(line) > 50:
            line = line[:50] + "..."

        return line

    @property
    def full_name(self):
        if self.parent is None:
            return self.name

        else:
            return (self.parent.full_name + " " + self.name).strip()

    def fill_module(self, module):
        self.module = module
        for cmd in self.commands:
            cmd.fill_module(module)

        for resume in self.resumes:
            resume.fill_module(module)

    async def execute(self, ctx, parts):
        ctx.last_cmd = self
        default = []
        args = []
        kwargs = {}

        for parameter in self.parameters:
            if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
                args.extend(parameter.parse(parts))

            elif parameter.kind == inspect.Parameter.VAR_KEYWORD:
                kwargs.update(parameter.parse(parts))

            elif parameter.kind == inspect.Parameter.KEYWORD_ONLY:
                kwargs[parameter.name] = parameter.parse(parts)

            else:
                default.append(parameter.parse(parts))

        for check in self.checks:
            await check.run(ctx, *default, *args, **kwargs)

        if self._cooldown is not None:
            await self._cooldown.run(ctx, *default, *args, **kwargs)

        if self.module is None:
            res = self.callback(ctx, *default, *args, **kwargs)

        else:
            res = self.callback(self.module, ctx, *default, *args, **kwargs)

        if inspect.isawaitable(res):
            return await res

        return res
