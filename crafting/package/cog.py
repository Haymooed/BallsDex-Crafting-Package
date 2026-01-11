from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

import discord
from asgiref.sync import sync_to_async
from discord import app_commands
from discord.ext import commands
from django.db import transaction
from django.utils import timezone

from bd_models.models import BallInstance, Player
from ..models import (
    CraftingIngredient,
    CraftingProfile,
    CraftingRecipe,
    CraftingRecipeState,
    CraftingSettings,
)

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

Interaction = discord.Interaction["BallsDexBot"]


def format_seconds(seconds: float) -> str:
    """Format seconds as a human friendly string."""
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"
    minutes, sec = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {sec}s"
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m"


async def get_settings() -> CraftingSettings:
    """Load crafting settings in async context."""
    return await sync_to_async(CraftingSettings.get_solo)()


async def ensure_player(user: discord.abc.User) -> Player:
    """Ensure a Player row exists for a Discord user."""
    player, _ = await Player.objects.aget_or_create(discord_id=user.id)
    return player


async def ensure_profile(player: Player) -> CraftingProfile:
    profile, _ = await CraftingProfile.objects.aget_or_create(player=player)
    return profile


async def ensure_state(player: Player, recipe: CraftingRecipe) -> CraftingRecipeState:
    state, _ = await CraftingRecipeState.objects.aget_or_create(player=player, recipe=recipe)
    return state


async def recipe_autocomplete(interaction: Interaction, current: str) -> list[app_commands.Choice[str]]:
    """Autocomplete enabled recipe names."""
    recipes = CraftingRecipe.objects.filter(enabled=True).order_by("name")
    recipe_names = await sync_to_async(list)(recipes.values_list("name", flat=True))
    if current:
        recipe_names = [name for name in recipe_names if current.lower() in name.lower()]
    return [app_commands.Choice(name=name, value=name) for name in recipe_names[:25]]


@dataclass
class CraftOutcome:
    success: bool
    message: str
    next_retry_after: float | None = None
    result_summary: str | None = None


class CraftingCog(commands.GroupCog, name="craft"):
    """Simple crafting system - combine balls to get new balls."""

    def __init__(self, bot: "BallsDexBot"):
        super().__init__()
        self.bot = bot

    # ----- Internal helpers -----

    async def _get_recipe(self, name: str) -> CraftingRecipe | None:
        try:
            return await CraftingRecipe.objects.select_related("result_ball", "result_special").prefetch_related(
                "ingredients__ball"
            ).aget(name__iexact=name)
        except CraftingRecipe.DoesNotExist:
            return None

    async def _collect_ingredients(self, recipe: CraftingRecipe) -> list[CraftingIngredient]:
        return await sync_to_async(list)(recipe.ingredients.select_related("ball").all())

    async def _check_cooldowns(
        self,
        settings: CraftingSettings,
        profile: CraftingProfile,
        state: CraftingRecipeState,
        recipe: CraftingRecipe,
    ) -> tuple[bool, float]:
        now = timezone.now()
        remaining = 0.0

        # Check global cooldown
        if profile.last_crafted_at:
            elapsed = (now - profile.last_crafted_at).total_seconds()
            required = settings.global_cooldown_seconds
            if elapsed < required:
                remaining = max(remaining, required - elapsed)

        # Check recipe cooldown
        if state.last_crafted_at:
            elapsed = (now - state.last_crafted_at).total_seconds()
            required = recipe.cooldown_seconds
            if elapsed < required:
                remaining = max(remaining, required - elapsed)

        return remaining == 0, remaining

    async def _check_requirements(
        self, player: Player, ingredients: list[CraftingIngredient]
    ) -> tuple[bool, str]:
        """Check if player has all required ingredients."""
        for ingredient in ingredients:
            count = await BallInstance.objects.filter(
                player=player, ball=ingredient.ball, deleted=False
            ).acount()
            if count < ingredient.quantity:
                return False, f"You need {ingredient.quantity} × {ingredient.ball.country}, but you only have {count}."
        return True, ""

    async def _consume_ingredients(self, player: Player, ingredients: list[CraftingIngredient]) -> None:
        """Consume required ball instances."""
        for ingredient in ingredients:
            qs = BallInstance.objects.filter(
                player=player, ball=ingredient.ball, deleted=False
            ).order_by("catch_date")
            ids = await sync_to_async(list)(qs.values_list("id", flat=True)[: ingredient.quantity])
            if len(ids) < ingredient.quantity:
                raise RuntimeError("Insufficient ball instances during consumption.")
            await BallInstance.objects.filter(id__in=ids).aupdate(deleted=True)

    async def _grant_result(self, player: Player, recipe: CraftingRecipe) -> str:
        """Grant crafted reward."""
        ball = recipe.result_ball
        if not ball:
            raise RuntimeError("Recipe missing ball result.")

        created_ids: list[int] = []
        for _ in range(recipe.result_quantity):
            new_instance = await BallInstance.objects.acreate(
                ball=ball,
                player=player,
                special=recipe.result_special,
                attack_bonus=0,
                health_bonus=0,
                spawned_time=timezone.now(),
                catch_date=timezone.now(),
            )
            created_ids.append(new_instance.pk)

        ids_display = ", ".join(f"#{pk:0X}" for pk in created_ids)
        special_suffix = f" with {recipe.result_special.name}" if recipe.result_special else ""
        return f"Crafted {recipe.result_quantity} × {ball.country}{special_suffix}\n**Pixels:** {ids_display}"

    async def _log_attempt(self, player: Player, recipe: CraftingRecipe, outcome: CraftOutcome) -> None:
        await CraftingLog.objects.acreate(
            player=player,
            recipe=recipe,
            success=outcome.success,
            message=outcome.message,
        )

    async def _perform_craft(
        self, player: Player, recipe: CraftingRecipe, *, allow_auto: bool = False
    ) -> CraftOutcome:
        """Execute a craft attempt including validation and consumption."""
        settings = await get_settings()
        if not settings.enabled:
            return CraftOutcome(False, "Crafting is currently disabled by admins.")
        if not recipe.enabled:
            return CraftOutcome(False, "That recipe is disabled.")
        if allow_auto:
            if not settings.allow_auto_crafting:
                return CraftOutcome(False, "Auto-crafting is disabled by admins.")
            if not recipe.allow_auto:
                return CraftOutcome(False, "Auto-crafting is disabled for this recipe.")

        profile = await ensure_profile(player)
        state = await ensure_state(player, recipe)
        ready, remaining = await self._check_cooldowns(settings, profile, state, recipe)
        if not ready:
            return CraftOutcome(
                False,
                f"Recipe is on cooldown. Try again in {format_seconds(remaining)}.",
                next_retry_after=remaining,
            )

        ingredients = await self._collect_ingredients(recipe)
        ok, reason = await self._check_requirements(player, ingredients)
        if not ok:
            return CraftOutcome(False, reason)

        # Wrap transaction in sync function since transaction.atomic() doesn't support async
        async def do_craft():
            # Do the async operations first
            await self._consume_ingredients(player, ingredients)
            result = await self._grant_result(player, recipe)

            # Update cooldowns in a sync transaction
            def update_cooldowns():
                with transaction.atomic():
                    state.update_cooldown()
                    profile.update_cooldown()
                    state.save(update_fields=("last_crafted_at",))
                    profile.save(update_fields=("last_crafted_at",))

            await sync_to_async(update_cooldowns)()
            return result

        result = await do_craft()
        return CraftOutcome(True, "Craft successful!", result_summary=result)

    def _recipe_embed(
        self, recipe: CraftingRecipe, ingredients: list[CraftingIngredient]
    ) -> discord.Embed:
        embed = discord.Embed(title=recipe.name, description=recipe.description or "No description provided.")
        
        # Ingredients
        ingredients_text = "\n".join(f"{i.quantity} × {i.ball.country}" for i in ingredients) or "None"
        embed.add_field(name="Ingredients", value=ingredients_text, inline=False)
        
        # Result
        if recipe.result_ball:
            special = f" with {recipe.result_special.name}" if recipe.result_special else ""
            result = f"{recipe.result_quantity} × {recipe.result_ball.country}{special}"
            embed.add_field(name="Result", value=result, inline=False)
        
        cooldown_text = format_seconds(recipe.cooldown_seconds) if recipe.cooldown_seconds else "None"
        embed.add_field(name="Cooldown", value=cooldown_text, inline=True)
        embed.add_field(name="Auto-Craft", value="✅ Enabled" if recipe.allow_auto else "❌ Disabled", inline=True)
        return embed

    # ----- Commands -----

    @app_commands.command(name="view", description="View all available crafting recipes.")
    @app_commands.checks.bot_has_permissions(send_messages=True, embed_links=True)
    async def craft_view(self, interaction: Interaction):
        settings = await get_settings()
        if not settings.enabled:
            await interaction.response.send_message("Crafting is currently disabled.", ephemeral=True)
            return

        recipes = await sync_to_async(list)(
            CraftingRecipe.objects.filter(enabled=True)
            .select_related("result_ball", "result_special")
            .prefetch_related("ingredients__ball")
        )
        if not recipes:
            await interaction.response.send_message("No crafting recipes are available right now.", ephemeral=True)
            return

        # Get ingredients for each recipe using prefetched data
        def get_ingredients(recipe: CraftingRecipe) -> list[CraftingIngredient]:
            return list(recipe.ingredients.all())

        embeds = []
        for recipe in recipes[:10]:
            ingredients_list = await sync_to_async(get_ingredients)(recipe)
            embeds.append(self._recipe_embed(recipe, ingredients_list))

        await interaction.response.send_message(embeds=embeds, ephemeral=True)

    @app_commands.command(description="Craft a recipe if requirements are met.")
    @app_commands.describe(recipe="Recipe name to craft")
    @app_commands.autocomplete(recipe=recipe_autocomplete)
    @app_commands.checks.bot_has_permissions(send_messages=True, embed_links=True)
    async def craft(self, interaction: Interaction, recipe: str):
        await interaction.response.defer(thinking=True)
        recipe_obj = await self._get_recipe(recipe)
        if not recipe_obj:
            await interaction.followup.send(f"Recipe '{recipe}' was not found.", ephemeral=True)
            return

        player = await ensure_player(interaction.user)
        outcome = await self._perform_craft(player, recipe_obj, allow_auto=False)
        await self._log_attempt(player, recipe_obj, outcome)

        if outcome.success:
            ingredients = await self._collect_ingredients(recipe_obj)
            embed = self._recipe_embed(recipe_obj, ingredients)
            embed.color = discord.Color.green()
            embed.add_field(name="Result", value=outcome.result_summary or "Crafted!", inline=False)
            await interaction.followup.send(f"✅ {outcome.message}", embed=embed)
        else:
            await interaction.followup.send(f"❌ {outcome.message}", ephemeral=True)

    @app_commands.command(name="auto", description="Enable or disable auto-crafting for a recipe.")
    @app_commands.describe(
        recipe="Recipe name to auto-craft (or 'off' to disable)",
        loops="Number of times to auto-craft (default: unlimited)"
    )
    @app_commands.autocomplete(recipe=recipe_autocomplete)
    @app_commands.checks.bot_has_permissions(send_messages=True, embed_links=True)
    async def craft_auto(
        self, interaction: Interaction, recipe: str, loops: int | None = None
    ):
        await interaction.response.defer(thinking=True)

        if recipe.lower() in ("off", "0", "none", "disable"):
            # Disable all auto-crafting
            states = await sync_to_async(list)(
                CraftingRecipeState.objects.filter(
                    player__discord_id=interaction.user.id, auto_enabled=True
                ).select_related("recipe")
            )
            if not states:
                await interaction.followup.send("You don't have any auto-crafting enabled.", ephemeral=True)
                return

            for state in states:
                state.auto_enabled = False
                await state.asave(update_fields=("auto_enabled",))

            await interaction.followup.send("✅ Disabled all auto-crafting.", ephemeral=True)
            return

        recipe_obj = await self._get_recipe(recipe)
        if not recipe_obj:
            await interaction.followup.send(f"Recipe '{recipe}' was not found.", ephemeral=True)
            return

        player = await ensure_player(interaction.user)
        state = await ensure_state(player, recipe_obj)

        settings = await get_settings()
        if not settings.allow_auto_crafting:
            await interaction.followup.send("Auto-crafting is disabled by admins.", ephemeral=True)
            return
        if not recipe_obj.allow_auto:
            await interaction.followup.send("Auto-crafting is disabled for this recipe.", ephemeral=True)
            return

        # Enable auto-crafting
        state.auto_enabled = True
        await state.asave(update_fields=("auto_enabled",))

        max_loops = loops if loops else 999999
        crafted = 0
        outcome = None

        for _ in range(max_loops):
            outcome = await self._perform_craft(player, recipe_obj, allow_auto=True)
            if not outcome.success:
                break
            crafted += 1
            await asyncio.sleep(0.5)  # Small delay between crafts

        if outcome and outcome.success:
            msg = f"Auto-crafted {crafted} time(s). Last result: {outcome.result_summary}"
            await interaction.followup.send(msg, ephemeral=True)
        elif outcome:
            await interaction.followup.send(
                f"Auto-crafting stopped: {outcome.message} (crafted {crafted} time(s)).", ephemeral=True
            )
        else:
            await interaction.followup.send("Auto-crafting finished with no attempts.", ephemeral=True)

        # Disable after completion
        state.auto_enabled = False
        await state.asave(update_fields=("auto_enabled",))
