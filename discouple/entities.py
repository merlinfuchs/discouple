from datetime import datetime


DISCORD_EPOCH = 1420070400000


class Snowflake:
    __slots__ = ("id",)

    def __init__(self, id):
        self.id = id

    def __hash__(self):
        return int(self.id) >> 22

    def __eq__(self, other):
        return isinstance(other, self.__class__) and other.id == self.id

    def __ne__(self, other):
        if isinstance(other, self.__class__):
            return other.id != self.id

        return True

    @property
    def created_at(self):
        return datetime.utcfromtimestamp(((int(self.id) >> 22) + DISCORD_EPOCH) / 1000)