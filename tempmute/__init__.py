from .tempmute import timedmutes


async def setup(bot):
    cog = timedmutes(bot)
    bot.add_cog(cog)
    await cog.initialize()
