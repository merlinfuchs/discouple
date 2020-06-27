from enum import IntEnum


class GuildVerificationLevel(IntEnum):
    NONE = 0
    LOW = 1
    MEDION = 2
    HIGH = 3
    VERY_HIGH = 4


class GuildMessageNotificationLevel(IntEnum):
    ALL_MESSAGES = 0
    ONLY_MENTIONS = 1


class GuildContentFilterLevel(IntEnum):
    DISABLED = 0
    MEMBERS_WITHOUT_ROLES = 1
    ALL_MEMBERS = 2


class MFALevel(IntEnum):
    NONE = 0
    ELEVATED = 1


class GuildPremiumTier(IntEnum):
    NONE = 0
    TIER_1 = 1
    TIER_2 = 2
    TIER_3 = 3


class UserPremiumType(IntEnum):
    NONE = 0
    NITRO_CLASSIC = 1
    NITRO = 2


class ChannelType(IntEnum):
    GUILD_TEXT = 0
    DM = 1
    GUILD_VOICE = 2
    GROUP_DM = 3
    GUILD_CATEGORY = 4
    GUILD_NEWS = 5
    GUILD_STORE = 6
