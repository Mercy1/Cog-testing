from .mod import Mod


async def setup(bot):
    cog = sinmod(bot)
    bot.add_cog(cog)
    await cog.initialize()
