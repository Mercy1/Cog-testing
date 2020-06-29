from .mod import Mod


async def setup(bot):
    cog = tempmute(bot)
    bot.add_cog(cog)
    await cog.initialize()
