import inspect


__all__ = (
    "maybe_coroutine",
    "AsyncIterator",
    "EmbedField",
    "EmbedAuthor",
    "EmbedFooter",
    "Embed"
)


async def maybe_coroutine(coro):
    if inspect.isawaitable(coro):
        return await coro

    return coro


class AsyncIterator:
    def __init__(self, to_wrap):
        self._to_wrap = to_wrap

    def __aiter__(self):
        return self

    def __anext__(self):
        return self._to_wrap.__anext__()

    async def flatten(self):
        return [item async for item in self]

    async def filter(self, predicate):
        async def _new_iterator():
            async for item in self:
                if await maybe_coroutine(predicate(item)):
                    yield item

        return AsyncIterator(_new_iterator())

    async def find(self, predicate):
        async for item in self:
            if await maybe_coroutine(predicate(item)):
                return item

        return None

    async def get(self, **attrs):
        def _predicate(item):
            for attr, value in attrs.items():
                nested = attr.split("__")
                element = item
                for a in nested:
                    element = getattr(element, a)

                if element != value:
                    return False

            return True

        return self.find(_predicate)

    async def map(self, func):
        async def _new_iterator():
            async for item in self:
                yield func(item)

        return AsyncIterator(_new_iterator())


class EmbedField:
    __slots__ = ("name", "value", "inline")

    def __init__(self, name, value, inline=True):
        self.name = name
        self.value = value
        self.inline = inline

    @property
    def json(self):
        return {
            "name": self.name,
            "value": self.value,
            "inline": self.inline
        }


class EmbedFooter:
    __slots__ = ("text", "icon_url")

    def __init__(self, text, icon_url=None):
        self.text = text
        self.icon_url = icon_url

    @property
    def json(self):
        return {
            "text": self.text,
            "icon_url": self.icon_url
        }


class EmbedAuthor:
    __slots__ = ("name", "url", "icon_url")

    def __init__(self, name=None, url=None, icon_url=None):
        self.name = name
        self.url = url
        self.icon_url = icon_url

    @property
    def json(self):
        return {
            "name": self.name,
            "url": self.url,
            "icon_url": self.icon_url
        }


class Embed:
    __slots__ = ("title", "description", "url", "color", "timestamp", "fields", "footer", "author")

    def __init__(self, title=None, description=None, url=None, color=None, timestamp=None):
        self.title = title
        self.description = description
        self.url = url
        self.color = color
        self.timestamp = timestamp
        self.fields = []
        self.footer = None
        self.author = None

    def add_field(self, *args, **kwargs):
        self.fields.append(EmbedField(*args, **kwargs))

    @property
    def json(self):
        return {
            "title": self.title,
            "description": self.description,
            "url": self.url,
            "color": self.color,
            "timestamp": self.timestamp,
            "fields": [f.json for f in self.fields],
            "footer": self.footer.json if self.footer is not None else None,
            "author": self.author.json if self.author is not None else None
        }
