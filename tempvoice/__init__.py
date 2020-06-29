import asyncio
import logging
from abc import ABCMeta
from datetime import timedelta
from typing import Optional

from discord.ext.commands import CogMeta as DPYCogMeta
from redbot.core import Config, commands

log = logging.getLogger("red.shino.relays")


# This previously used ``(type(commands.Cog), type(ABC))``
# This was changed to be explicit so that mypy would be slightly happier about it.
# This does introduce a potential place this can break in the future, but this would be an
# Upstream breaking change announced in advance



from .mycog import tempvoice

def setup(bot):
    bot.add_cog(tempvoice())
