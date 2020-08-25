from .loa import LOACog


def setup(bot):
    bot.add_cog(LOACog(bot))