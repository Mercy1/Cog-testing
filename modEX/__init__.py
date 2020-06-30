from redbot.core.bot import Red
from .modEX import ModEX


async def setup(bot: Red):
    cog = ModEX(bot)
    bot.add_cog(cog)
    await cog.initialize()
