import asyncio
from collections import deque
from time import time

from telethon.errors import UserNotParticipantError
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.types import Channel, Chat
from telethon.utils import get_display_name

from . import *


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Having Cache of frequently used stuff.

BANNED_USERS = set()
BOT_USERS = list()
MESSAGE_IDS = dict()

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~


class Cache:
    sleepTime = 600

    def __init__(
        self,
        maxlen=None,  # max len of cache
        auto_clear=None,  # clear cache time (s)
    ):
        self.cleaner = auto_clear
        self.data = deque(maxlen=maxlen)
        if self.cleaner:
            self.task = asyncio.create_task(self.handle_cleanups())

    def add_data(self, data):
        if self.cleaner:
            data = (data, time())
        self.data.append(data)

    def __call__(self):
        return self.data

    async def handle_cleanups(self):
        while True:
            await asyncio.sleep(self.sleepTime)
            for data, s_time in self.data:
                if time() - s_time > self.cleaner:
                    try:
                        self.data.remove((data, s_time))
                    except ValueError:
                        pass


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Force Subscribe handlers

FSUBBED_USERS = Cache(maxlen=200, auto_clear=6 * 60 * 60)
FSUB_CHANNEL = Cache(maxlen=1, auto_clear=10800)

# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Fsub Helpers
async def set_fsub_chat():
    try:
        entity = await bot.get_entity(Config.FORCE_SUBSCRIBE)
        username = getattr(entity, "username", None)

        if username:
            invite_link = f"https://t.me/{username}"
        else:
            if isinstance(entity, Channel):
                full = await bot(GetFullChannelRequest(Config.FORCE_SUBSCRIBE))
            elif isinstance(entity, Chat):
                full = await bot(GetFullChatRequest(Config.FORCE_SUBSCRIBE))
            else:
                raise TypeError("Invalid Chat Type..")

            if full.full_chat.exported_invite:
                invite_link = full.full_chat.exported_invite.link
            else:
                raise TypeError("Invite User Permission Missing..")

        FSUB_CHANNEL.add_data(invite_link)
        return entity
    except Exception:
        LOGS.exception("Error in FORCE_SUBSCRIBE:")


def _check_if_subbed_(user_id):
    users = FSUBBED_USERS()
    user = filter(lambda n: n[0] == user_id, users)
    return bool(list(user))


async def fsub_checker(user_id):
    if not FSUB_CHANNEL():
        await set_fsub_chat()
    if (
        user_id == Config.OWNER_ID
        or _check_if_subbed_(user_id)
        or not FSUB_CHANNEL()  # fsub error
    ):
        return True
    try:
        await bot.get_permissions(Config.FORCE_SUBSCRIBE, user_id)
        FSUBBED_USERS.add_data(user_id)
        return True
    except UserNotParticipantError:
        return


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# Helper Functions


def mention(user):
    username = getattr(user, "username", None)
    if username:
        return "@" + username
    fullname = get_display_name(user)
    return f"[{fullname}](tg://user?id={user.id})"


def time_formatter(ms):
    minutes, seconds = divmod(int(ms / 1000), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    weeks, days = divmod(days, 7)
    tmp = (
        ((str(weeks) + "w:") if weeks else "")
        + ((str(days) + "d:") if days else "")
        + ((str(hours) + "h:") if hours else "")
        + ((str(minutes) + "m:") if minutes else "")
        + ((str(seconds) + "s") if seconds else "")
    )
    if not tmp:
        return "0s"
    return tmp[:-1] if tmp.endswith(":") else tmp


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

# DB Helpers


async def save_msg_id(msg_id, user_id):
    key = "_PMBOT_MESSAGE_IDS"
    MESSAGE_IDS.update({msg_id: user_id})
    await redis.set_key(key, MESSAGE_IDS)


async def add_user_to_db(user_id):
    global BOT_USERS
    key = "_PMBOT_USERS"
    if user_id not in BOT_USERS and user_id != Config.OWNER_ID:
        BOT_USERS.append(user_id)
        await redis.set_key(key, BOT_USERS)
