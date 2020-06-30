from .tempvoice import voice

async def setup(bot: commands.Bot):
    cog = voice(bot)
    bot.add_cog(cog)
