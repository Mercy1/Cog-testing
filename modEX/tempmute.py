import logging
import re
import collections
import discord
from datetime import datetime, timedelta
from typing import Optional
from redbot.core.commands.converter import TimedeltaConverter #sin add
from redbot.core.utils.predicates import MessagePredicate #sin add
from redbot.core.utils.chat_formatting import humanize_list, humanize_timedelta #sin added last 2
from redbot.core import commands, Config, checks, utils
from .abc import MixinMeta


log = logging.getLogger("red.Shino-cogs.tempmuute")

class Time(commands.Converter):
    TIME_AMNT_REGEX = re.compile("([1-9][0-9]*)([a-z]+)", re.IGNORECASE)
    TIME_QUANTITIES = collections.OrderedDict(
        [
            ("seconds", 1),
            ("minutes", 60),
            ("hours", 3600),
            ("days", 86400),
            ("weeks", 604800),
            ("months", 2.628e6),
            ("years", 3.154e7),
        ]
    )  # (amount in seconds, max amount)

    async def convert(self, ctx, arg):
        result = None
        seconds = self.get_seconds(arg)
        time_now = datetime.datetime.utcnow()
        days, secs = divmod(seconds, 3600 * 24)
        end_time = time_now + datetime.timedelta(days=days, seconds=secs)
        result = end_time
        if result is None:
            raise commands.BadArgument('Unable to parse Date "{}" '.format(arg))
        return result

    @classmethod
    async def fromString(cls, arg):
        seconds = cls.get_seconds(cls, arg)
        time_now = datetime.datetime.utcnow()
        if seconds is not None:
            days, secs = divmod(seconds, 3600 * 24)
            end_time = time_now + datetime.timedelta(days=days, seconds=secs)
            return end_time
        else:
            return None

    def get_seconds(self, time):
        """Returns the amount of converted time or None if invalid"""
        seconds = 0
        for time_match in self.TIME_AMNT_REGEX.finditer(time):
            time_amnt = int(time_match.group(1))
            time_abbrev = time_match.group(2)
            time_quantity = discord.utils.find(
                lambda t: t[0].startswith(time_abbrev), self.TIME_QUANTITIES.items()
            )
            if time_quantity is not None:
                seconds += time_amnt * time_quantity[1]
        return None if seconds == 0 else seconds

class hierarchy(MixinMeta):
    """hierarchy checks"""
async def hierarchy(self, ctx: commands.Context):
        """Toggle role hierarchy check for mods and admins.
        **WARNING**: Disabling this setting will allow mods to take
        actions on users above them in the role hierarchy!
        This is enabled by default.
        """
        guild = ctx.guild
        toggled = await self.settings.guild(guild).respect_hierarchy()
        if not toggled:
            await self.settings.guild(guild).respect_hierarchy.set(True)
            await ctx.send(
                _("Role hierarchy will be checked when moderation commands are issued.")
            )
        else:
            await self.settings.guild(guild).respect_hierarchy.set(False)
            await ctx.send(
                _("Role hierarchy will be ignored when moderation commands are issued.")
            )
    
    

class TempMutes(MixinMeta):
    """temp mutes"""

    def __init__(self, bot):
        super().__init__(bot)
        self.bot = bot
        self.__config = Config.get_conf(
            self, identifier=95932766180343808, force_registration=True
        )
        defaultsguild = {"muterole": None, "respect_hierarchy": True}
        defaults = {"muted": {}}
        self.__config.register_guild(**defaultsguild)
        self.__config.register_global(**defaults)
        self.loop = bot.loop.create_task(self.unmute_loop())

    async def unmute_loop(self):
        while True:
            muted = await self.__config.muted()
            for guild in muted:
                for user in muted[guild]:
                    if datetime.fromtimestamp(muted[guild][user]["expiry"]) < datetime.now():
                        await self.unmute(user, guild)
            await asyncio.sleep(15)

        #code for unmute loop
    async def roleunmute(self, user, guildid, *, moderator: discord.Member = None):
        guild = self.bot.get_guild(int(guildid))
        if guild is None:
            return
        mutedroleid = await self.__config.guild(guild).muterole()
        muterole = guild.get_role(mutedroleid)
        member = guild.get_member(int(user))
        if member is not None:
            if moderator is None:
                await member.remove_roles(muterole, reason="Mute expired.")
                log.info("Unmuted {} in {}.".format(member, guild))
            else:
                await member.remove_roles(muterole, reason="Unmuted by {}.".format(moderator))
                log.info("Unmuted {} in {} by {}.".format(member, guild, moderator))
            await log.create_case(
               self.bot,
                guild,
                datetime.utcnow(),
                "sunmute",
                member,
                moderator,
                "Automatic Unmute" if moderator is None else None,
            )
        else:
            log.info("{} is no longer in {}, removing from muted list.".format(user, guild))
        async with self.__config.muted() as muted:
          if user in muted[guildid]:
               del muted[guildid][user]
               
#code for mute role
    @checks.mod_or_permissions(manage_roles=True)
    @checks.bot_has_permissions(manage_roles=True)
    @commands.group(invoke_without_command=True)
    async def rolemute(
        self,
        ctx,
        users: commands.Greedy[discord.Member],
        duration: Optional[TimedeltaConverter] = None,
        *,
        reason: str = None,
    ):
        """Mute users."""
        if not users:
            return await ctx.send_help()
        if duration is None:
            duration = timedelta(minutes=10)
        duration_seconds = duration.total_seconds()
        guild = ctx.guild
        roleid = await self.__config.guild(guild).muterole()
        if roleid is None:
            await ctx.send(
                "There is currently no mute role set for this server. If you would like one to be automatically setup then type yes, otherwise type no then one can be set via {}mute roleset <role>".format(
                    ctx.prefix
                )
            )
            try:
                pred = MessagePredicate.yes_or_no(ctx, user=ctx.author)
                msg = await ctx.bot.wait_for("message", check=pred, timeout=60)
            except asyncio.TimeoutError:
                return await ctx.send("Alright, cancelling the operation.")

            if pred.result:
                await msg.add_reaction("\N{WHITE HEAVY CHECK MARK}")
                await self.create_muted_role(guild)
                roleid = await self.__config.guild(guild).muterole()
            else:
                await msg.add_reaction("\N{WHITE HEAVY CHECK MARK}")
                return
        mutedrole = guild.get_role(roleid)
        if mutedrole is None:
            return await ctx.send(
                f"The mute role for this server is invalid. Please set one up using {ctx.prefix}mute roleset <role>."
            )
        completed = []
        failed = []
        async with self.__config.muted() as muted:
            if str(ctx.guild.id) not in muted:
                muted[str(ctx.guild.id)] = {}
            for user in users:
                if user == ctx.author:
                    failed.append(f"{user} - Self harm is bad.")
                    continue
                if not await respect_hierarchy(
                    self.bot, self.__config, guild, ctx.author, user
                ):
                    failed.append(
                        f"{user} - You are not higher than this user in the role hierarchy"
                    )
                    continue
                if guild.me.top_role <= user.top_role or user == guild.owner:
                    failed.append(
                        f"{user} - Discord hierarcy rules prevent you from muting this user."
                    )
                    continue
                await user.add_roles(
                    mutedrole,
                    reason="Muted by {} for {}{}".format(
                        ctx.author,
                        humanize_timedelta(timedelta=duration),
                        f" | Reason: {reason}" if reason is not None else "",
                    ),
                )
                expiry = datetime.now() + timedelta(seconds=duration_seconds)
                muted[str(ctx.guild.id)][str(user.id)] = {
                    "time": datetime.now().timestamp(),
                    "expiry": expiry.timestamp(),
                }
                await log.create_case(
                    ctx.bot,
                    ctx.guild,
                    ctx.message.created_at,
                    "smute",
                    user,
                    ctx.author,
                    reason,
                    expiry,
                )
                log.info(
                    f"{user} muted by {ctx.author} in {ctx.guild} for {humanize_timedelta(timedelta=duration)}"
                )
                completed.append(user)
        msg = "{}".format("\n**Reason**: {}".format(reason) if reason is not None else "")
        if completed:
            await ctx.send(
                f"`{humanize_list([str(x) for x in completed])}` has been muted for {humanize_timedelta(timedelta=duration)}.{msg}"
            )
        if failed:
            failemsg = "\n{}".format("\n".join(failed))
            await ctx.send(
                f"{len(failed)} user{'s' if len(failed) > 1 else ''} failed to be muted for the following reasons.{failemsg}"
            )        
#commands
    @commands.group()
    async def role(self, ctx: commands.Context):
        """Temp mutes role"""
        pass

    @commands.bot_has_permissions(manage_roles=True)
    @checks.mod_or_permissions(manage_channels=True)
    @rolemute.command()
    async def roleset(self, ctx, role: discord.Role):
        """Set a mute role."""
        await self.__config.guild(ctx.guild).muterole.set(role.id)
        await ctx.send("The muted role has been set to {}".format(role.name))


    @commands.bot_has_permissions(manage_roles=True)
    @checks.mod_or_permissions(manage_channels=True)
    #@role.command()     
    @commands.group(invoke_without_command=True, name="roleunmute")
    async def _roleunmute(self, ctx, users: commands.Greedy[discord.Member]):
        """Unmute users."""
        muted = await self.__config.muted()
        for user in users:
            if str(ctx.guild.id) not in muted:
                return await ctx.send("There is nobody currently muted in this server.")
        await self.unmute(str(user.id), str(ctx.guild.id))
        await ctx.tick()           

    @commands.bot_has_permissions(manage_roles=True)
    @checks.mod_or_permissions(manage_channels=True)
    @role.command(name="list")
    async def _list(self, ctx):
        """List those who are muted."""
        muted = await self.__config.muted()
        guildmuted = muted.get(str(ctx.guild.id))
        if guildmuted is None:
            return await ctx.send("There is currently nobody muted in {}".format(ctx.guild))
        msg = ""
        for user in guildmuted:
            expiry = datetime.fromtimestamp(guildmuted[user]["expiry"]) - datetime.now()
            msg += f"{self.bot.get_user(int(user)).mention} is muted for {humanize_timedelta(timedelta=expiry)}\n"
        await ctx.maybe_send_embed(msg if msg else "Nobody is currently muted.")
# thank god this took time ^^        

