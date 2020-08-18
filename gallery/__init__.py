from .gallery import Gallery

__red_end_user_data_statement__ = (
    "This cog does not store any user data, all this cog is actively responsable for is allowing image only channels."
    "It will not respect data deletion by end users as no data is stored."
)


def setup(bot):
    bot.add_cog(Gallery(bot))
