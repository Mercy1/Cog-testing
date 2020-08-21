import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import discord
from redbot.cogs.mod import Mod as tempmute
from redbot.core import Config, checks, commands, modlog
from redbot.core.commands.converter import TimedeltaConverter
from redbot.core.utils.chat_formatting import humanize_list, humanize_timedelta
from redbot.core.utils.mod import is_allowed_by_hierarchy
from redbot.core.utils.predicates import MessagePredicate
from .mutes import MuteMixin
from .events import Events
from .kickban import KickBanMixin
from .names import ModInfo
from .slowmode import Slowmode
from .settings import ModSettings
from .abc import timedmutes

class timedmutes(timedmutes, commands.Cog):
    """Mod with timed mute."""

    __version__ = "1.0.0"

    def format_help_for_context(self, ctx):
        """Thanks Sinbad."""
        pre_processed = super().format_help_for_context(ctx)
        return f"{pre_processed}\nCog Version: {self.__version__}"

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.__config = Config.get_conf(
            self, identifier=95932766180343808, force_registration=True
        )
    @commands.command()
    async def rolemute(self, ctx, members: commands.Greedy[discord.Member],
                   mute_minutes: typing.Optional[int] = 0,
                   *, reason: str = "None"):
     """Mass mute members with an optional mute_minutes parameter to time it"""

    if not members:
        await ctx.send("You need to name someone to mute")
        return

    muted_role = discord.utils.find(ctx.guild.roles, name="Muted")

    for member in members:
        if self.bot.user == member: # what good is a muted bot?
            embed = discord.Embed(title = "You can't mute me, I'm an almighty bot")
            await ctx.send(embed = embed)
            continue
        await member.add_roles(muted_role, reason = reason)
        await ctx.send("{0.mention} has been muted by {1.mention} for *{2}*".format(member, ctx.author, reason))

    if mute_minutes > 0:
        await asyncio.sleep(mute_minutes * 60)
        for member in members:
            await member.remove_roles(muted_role, reason = "time's up ")
