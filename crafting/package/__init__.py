from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot


async def setup(bot: "BallsDexBot"):
    """Setup entrypoint for the crafting package."""
    from .cog import CraftingCog

    await bot.add_cog(CraftingCog(bot))

