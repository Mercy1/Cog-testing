import asyncio
from typing import cast, Optional

import logging #Sin add
import discord
from redbot.core import commands, checks, i18n, modlog, Config
from redbot.core.utils.chat_formatting import format_perms_list, humanize_list, humanize_timedelta #sin added last 2
from redbot.core.utils.mod import get_audit_reason, is_allowed_by_hierarchy
from redbot.core.commands.converter import TimedeltaConverter #sin add
from datetime import datetime, timedelta #sin add
from .abc import MixinMeta

T_ = i18n.Translator("Mod", __file__)

_ = lambda s: s
mute_unmute_issues = {
    "already_muted": _("That user can't send messages in this channel."),
    "already_unmuted": _("That user isn't muted in this channel."),
    "hierarchy_problem": _(
        "I cannot let you do that. You are not higher than the user in the role hierarchy."
    ),
    "is_admin": _("That user cannot be muted, as they have the Administrator permission."),
    "permissions_issue": _(
        "Failed to mute user. I need the manage roles "
        "permission and the user I'm muting must be "
        "lower than myself in the role hierarchy."
    ),
}
_ = T_


class MuteMixin(MixinMeta):
    """
    Stuff for mutes goes here
    """

    @staticmethod
    async def _voice_perm_check(
        ctx: commands.Context, user_voice_state: Optional[discord.VoiceState], **perms: bool
    ) -> bool:
        """Check if the bot and user have sufficient permissions for voicebans.

        This also verifies that the user's voice state and connected
        channel are not ``None``.

        Returns
        -------
        bool
            ``True`` if the permissions are sufficient and the user has
            a valid voice state.

        """
        if user_voice_state is None or user_voice_state.channel is None:
            await ctx.send(_("That user is not in a voice channel."))
            return False
        voice_channel: discord.VoiceChannel = user_voice_state.channel
        required_perms = discord.Permissions()
        required_perms.update(**perms)
        if not voice_channel.permissions_for(ctx.me) >= required_perms:
            await ctx.send(
                _("I require the {perms} permission(s) in that user's channel to do that.").format(
                    perms=format_perms_list(required_perms)
                )
            )
            return False
        if (
            ctx.permission_state is commands.PermState.NORMAL
            and not voice_channel.permissions_for(ctx.author) >= required_perms
        ):
            await ctx.send(
                _(
                    "You must have the {perms} permission(s) in that user's channel to use this "
                    "command."
                ).format(perms=format_perms_list(required_perms))
            )
            return False
        return True

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(mute_members=True, deafen_members=True)
    async def voiceunban(self, ctx: commands.Context, user: discord.Member, *, reason: str = None):
        """Unban a user from speaking and listening in the server's voice channels."""
        user_voice_state = user.voice
        if (
            await self._voice_perm_check(
                ctx, user_voice_state, deafen_members=True, mute_members=True
            )
            is False
        ):
            return
        needs_unmute = True if user_voice_state.mute else False
        needs_undeafen = True if user_voice_state.deaf else False
        audit_reason = get_audit_reason(ctx.author, reason)
        if needs_unmute and needs_undeafen:
            await user.edit(mute=False, deafen=False, reason=audit_reason)
        elif needs_unmute:
            await user.edit(mute=False, reason=audit_reason)
        elif needs_undeafen:
            await user.edit(deafen=False, reason=audit_reason)
        else:
            await ctx.send(_("That user isn't muted or deafened by the server!"))
            return

        guild = ctx.guild
        author = ctx.author
        try:
            await modlog.create_case(
                self.bot,
                guild,
                ctx.message.created_at,
                "voiceunban",
                user,
                author,
                reason,
                until=None,
                channel=None,
            )
        except RuntimeError as e:
            await ctx.send(e)
        await ctx.send(_("User is now allowed to speak and listen in voice channels"))

    @commands.command()
    @commands.guild_only()
    @checks.admin_or_permissions(mute_members=True, deafen_members=True)
    async def voiceban(self, ctx: commands.Context, user: discord.Member, *, reason: str = None):
        """Ban a user from speaking and listening in the server's voice channels."""
        user_voice_state: discord.VoiceState = user.voice
        if (
            await self._voice_perm_check(
                ctx, user_voice_state, deafen_members=True, mute_members=True
            )
            is False
        ):
            return
        needs_mute = True if user_voice_state.mute is False else False
        needs_deafen = True if user_voice_state.deaf is False else False
        audit_reason = get_audit_reason(ctx.author, reason)
        author = ctx.author
        guild = ctx.guild
        if needs_mute and needs_deafen:
            await user.edit(mute=True, deafen=True, reason=audit_reason)
        elif needs_mute:
            await user.edit(mute=True, reason=audit_reason)
        elif needs_deafen:
            await user.edit(deafen=True, reason=audit_reason)
        else:
            await ctx.send(_("That user is already muted and deafened server-wide!"))
            return

        try:
            await modlog.create_case(
                self.bot,
                guild,
                ctx.message.created_at,
                "voiceban",
                user,
                author,
                reason,
                until=None,
                channel=None,
            )
        except RuntimeError as e:
            await ctx.send(e)
        await ctx.send(_("User has been banned from speaking or listening in voice channels"))

    @commands.group()
    @commands.guild_only()
    @checks.mod_or_permissions(manage_channels=True)
    async def mute(self, ctx: commands.Context):
        """Mute users."""
        pass

    @mute.command(name="voice")
    @commands.guild_only()
    async def voice_mute(self, ctx: commands.Context, user: discord.Member, *, reason: str = None):
        """Mute a user in their current voice channel."""
        user_voice_state = user.voice
        if (
            await self._voice_perm_check(
                ctx, user_voice_state, mute_members=True, manage_channels=True
            )
            is False
        ):
            return
        guild = ctx.guild
        author = ctx.author
        channel = user_voice_state.channel
        audit_reason = get_audit_reason(author, reason)

        success, issue = await self.mute_user(guild, channel, author, user, audit_reason)

        if success:
            try:
                await modlog.create_case(
                    self.bot,
                    guild,
                    ctx.message.created_at,
                    "vmute",
                    user,
                    author,
                    reason,
                    until=None,
                    channel=channel,
                )
            except RuntimeError as e:
                await ctx.send(e)
            await ctx.send(
                _("Muted {user} in channel {channel.name}").format(user=user, channel=channel)
            )
        else:
            await ctx.send(issue)

    @mute.command(name="channel")
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @checks.mod_or_permissions(administrator=True)
    async def channel_mute(
        self, ctx: commands.Context, user: discord.Member, *, reason: str = None
    ):
        """Mute a user in the current text channel."""
        author = ctx.message.author
        channel = ctx.message.channel
        guild = ctx.guild
        audit_reason = get_audit_reason(author, reason)

        success, issue = await self.mute_user(guild, channel, author, user, audit_reason)

        if success:
            try:
                await modlog.create_case(
                    self.bot,
                    guild,
                    ctx.message.created_at,
                    "cmute",
                    user,
                    author,
                    reason,
                    until=None,
                    channel=channel,
                )
            except RuntimeError as e:
                await ctx.send(e)
            await channel.send(_("User has been muted in this channel."))
        else:
            await channel.send(issue)

    @mute.command(name="server", aliases=["guild"])
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @checks.mod_or_permissions(administrator=True)
    async def guild_mute(self, ctx: commands.Context, user: discord.Member, *, reason: str = None):
        """Mutes user in the server"""
        author = ctx.message.author
        guild = ctx.guild
        audit_reason = get_audit_reason(author, reason)

        mute_success = []
        for channel in guild.channels:
            success, issue = await self.mute_user(guild, channel, author, user, audit_reason)
            mute_success.append((success, issue))
            await asyncio.sleep(0.1)
        try:
            await modlog.create_case(
                self.bot,
                guild,
                ctx.message.created_at,
                "smute",
                user,
                author,
                reason,
                until=None,
                channel=None,
            )
        except RuntimeError as e:
            await ctx.send(e)
        await ctx.send(_("User has been muted in this server."))

    @commands.group()
    @commands.guild_only()
    @commands.bot_has_permissions(manage_roles=True)
    @checks.mod_or_permissions(manage_channels=True)
    async def unmute(self, user, ctx: commands.Context):
        """Unmute users."""
        pass

    @unmute.command(name="voice")
    @commands.guild_only()
    async def unmute_voice(
        self, ctx: commands.Context, user: discord.Member, *, reason: str = None
    ):
        """Unmute a user in their current voice channel."""
        user_voice_state = user.voice
        if (
            await self._voice_perm_check(
                ctx, user_voice_state, mute_members=True, manage_channels=True
            )
            is False
        ):
            return
        guild = ctx.guild
        author = ctx.author
        channel = user_voice_state.channel
        audit_reason = get_audit_reason(author, reason)

        success, message = await self.unmute_user(guild, channel, author, user, audit_reason)

        if success:
            try:
                await modlog.create_case(
                    self.bot,
                    guild,
                    ctx.message.created_at,
                    "vunmute",
                    user,
                    author,
                    reason,
                    until=None,
                    channel=channel,
                )
            except RuntimeError as e:
                await ctx.send(e)
            await ctx.send(
                _("Unmuted {user} in channel {channel.name}").format(user=user, channel=channel)
            )
        else:
            await ctx.send(_("Unmute failed. Reason: {}").format(message))

    @checks.mod_or_permissions(administrator=True)
    @unmute.command(name="channel")
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def unmute_channel(
        self, ctx: commands.Context, user: discord.Member, *, reason: str = None
    ):
        """Unmute a user in this channel."""
        channel = ctx.channel
        author = ctx.author
        guild = ctx.guild
        audit_reason = get_audit_reason(author, reason)

        success, message = await self.unmute_user(guild, channel, author, user, audit_reason)

        if success:
            try:
                await modlog.create_case(
                    self.bot,
                    guild,
                    ctx.message.created_at,
                    "cunmute",
                    user,
                    author,
                    reason,
                    until=None,
                    channel=channel,
                )
            except RuntimeError as e:
                await ctx.send(e)
            await ctx.send(_("User unmuted in this channel."))
        else:
            await ctx.send(_("Unmute failed. Reason: {}").format(message))

    @checks.mod_or_permissions(administrator=True)
    @unmute.command(name="server", aliases=["guild"])
    @commands.bot_has_permissions(manage_roles=True)
    @commands.guild_only()
    async def unmute_guild(
        self, ctx: commands.Context, user: discord.Member, *, reason: str = None
    ):
        """Unmute a user in this server."""
        guild = ctx.guild
        author = ctx.author
        audit_reason = get_audit_reason(author, reason)

        unmute_success = []
        for channel in guild.channels:
            success, message = await self.unmute_user(guild, channel, author, user, audit_reason)
            unmute_success.append((success, message))
            await asyncio.sleep(0.1)
        try:
            await modlog.create_case(
                self.bot,
                guild,
                ctx.message.created_at,
                "sunmute",
                user,
                author,
                reason,
                until=None,
            )
        except RuntimeError as e:
            await ctx.send(e)
        await ctx.send(_("User has been unmuted in this server."))

    async def mute_user(
        self,
        guild: discord.Guild,
        channel: discord.abc.GuildChannel,
        author: discord.Member,
        user: discord.Member,
        reason: str,
    ) -> (bool, str):
        """Mutes the specified user in the specified channel"""
        overwrites = channel.overwrites_for(user)
        permissions = channel.permissions_for(user)

        if permissions.administrator:
            return False, _(mute_unmute_issues["is_admin"])

        new_overs = {}
        if not isinstance(channel, discord.TextChannel):
            new_overs.update(speak=False)
        if not isinstance(channel, discord.VoiceChannel):
            new_overs.update(send_messages=False, add_reactions=False)

        if all(getattr(permissions, p) is False for p in new_overs.keys()):
            return False, _(mute_unmute_issues["already_muted"])

        elif not await is_allowed_by_hierarchy(self.bot, self.settings, guild, author, user):
            return False, _(mute_unmute_issues["hierarchy_problem"])

        old_overs = {k: getattr(overwrites, k) for k in new_overs}
        overwrites.update(**new_overs)
        try:
            await channel.set_permissions(user, overwrite=overwrites, reason=reason)
        except discord.Forbidden:
            return False, _(mute_unmute_issues["permissions_issue"])
        else:
            await self.settings.member(user).set_raw(
                "perms_cache", str(channel.id), value=old_overs
            )
            return True, None

    async def unmute_user(
        self,
        guild: discord.Guild,
        channel: discord.abc.GuildChannel,
        author: discord.Member,
        user: discord.Member,
        reason: str,
    ) -> (bool, str):
        overwrites = channel.overwrites_for(user)
        perms_cache = await self.settings.member(user).perms_cache()

        if channel.id in perms_cache:
            old_values = perms_cache[channel.id]
        else:
            old_values = {"send_messages": None, "add_reactions": None, "speak": None}

        if all(getattr(overwrites, k) == v for k, v in old_values.items()):
            return False, _(mute_unmute_issues["already_unmuted"])

        elif not await is_allowed_by_hierarchy(self.bot, self.settings, guild, author, user):
            return False, _(mute_unmute_issues["hierarchy_problem"])

        overwrites.update(**old_values)
        try:
            if overwrites.is_empty():
                await channel.set_permissions(
                    user, overwrite=cast(discord.PermissionOverwrite, None), reason=reason
                )
            else:
                await channel.set_permissions(user, overwrite=overwrites, reason=reason)
        except discord.Forbidden:
            return False, _(mute_unmute_issues["permissions_issue"])
        else:
            await self.settings.member(user).clear_raw("perms_cache", str(channel.id))
            return True, None

class tempmute(MixinMeta):
    """
    Stuff for timed mutes goes here
    """
    #Sinon's code timed mutes below
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
        self.loop = bot.loop.create_task(self.roleunmute_loop())

    # Removes main mods mute commands.
    voice_mute = None
    channel_mute = None
    guild_mute = None
    unmute_voice = None
    unmute_channel = None
    unmute_guild = None
    # ban = None # TODO: Merge hackban and ban.

    async def roleunmute_loop(self):
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
                modlog.info("Unmuted {} in {}.".format(member, guild))
            else:
                await member.remove_roles(muterole, reason="Unmuted by {}.".format(moderator))
                modlog.info("Unmuted {} in {} by {}.".format(member, guild, moderator))
            await modlog.create_case(
               self.bot,
                guild,
                datetime.utcnow(),
                "sunmute",
                member,
                moderator,
                "Automatic Unmute" if moderator is None else None,
            )
        else:
            modlog.info("{} is no longer in {}, removing from muted list.".format(user, guild))
        async with self.__config.muted() as muted:
          if user in muted[guildid]:
               del muted[guildid][user]


    @commands.group()
    async def rolemute(self, ctx, users: commands.Greedy[discord.Member],
        duration: Optional[TimedeltaConverter] = None,
        *,
        reason: str = None,):
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
    @commands.group(invoke_without_command=True, name="roleunmute")
    async def _roleunmute(self, ctx, moderator:discord.member, users: commands.Greedy[discord.Member]):
        """Unmute users."""
        muted = await self.__config.muted()
        for user in users:
            if str(ctx.guild.id) not in muted:
                return await ctx.send("There is nobody currently muted in this server.")
        await self.unmute(str(user.id), str(ctx.guild.id))
        await ctx.tick()           

    @commands.bot_has_permissions(manage_roles=True)
    @checks.mod_or_permissions(manage_channels=True)
    @rolemute.command(name="list")
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
