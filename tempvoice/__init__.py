from .tempvoice import voice

async def setup(bot: voice.Bot):
    cog = voice(bot)
    bot.add_cog(cog)
