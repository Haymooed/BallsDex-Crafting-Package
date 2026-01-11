from __future__ import annotations

from datetime import timedelta
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
    CraftingRecipe,
    CraftingSession,
    CraftingSessionItem,
    CraftingSettings,
)

if TYPE_CHECKING:
    from ballsdex.core.bot import BallsDexBot

Interaction = discord.Interaction["BallsDexBot"]


async def get_settings() -> CraftingSettings:
    """Load crafting settings in async context."""
    return await sync_to_async(CraftingSettings.get_solo)()


async def ensure_player(user: discord.abc.User) -> Player:
    """Ensure a Player row exists for a Discord user."""
    player, _ = await Player.objects.aget_or_create(discord_id=user.id)
    return player


async def get_or_create_session(player: Player, settings: CraftingSettings) -> CraftingSession:
    """Get or create a crafting session for a player."""
    try:
        session = await CraftingSession.objects.select_related("player").prefetch_related(
            "items__ball_instance__ball"
        ).aget(player=player)
        if session.is_expired():
            # Delete expired session and create new one
            await session.adelete()
            raise CraftingSession.DoesNotExist
        return session
    except CraftingSession.DoesNotExist:
        expires_at = timezone.now() + timedelta(minutes=settings.session_timeout_minutes)
        session = await CraftingSession.objects.acreate(player=player, expires_at=expires_at)
        return session


class CraftView(discord.ui.View):
    """View with Craft and Cancel buttons for crafting session."""

    def __init__(self, cog: "CraftingCog", player: Player, session: CraftingSession):
        super().__init__(timeout=600)  # 10 minutes
        self.cog = cog
        self.player = player
        self.session = session

    @discord.ui.button(label="Craft", style=discord.ButtonStyle.green, emoji="🔨")
    async def craft_button(self, interaction: Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        result = await self.cog._perform_craft_from_session(self.player, self.session)
        if result["success"]:
            embed = discord.Embed(
                title="✅ Craft Successful!",
                description=result["message"],
                color=discord.Color.green(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            # Refresh the session view
            await self.cog._send_session_embed(interaction, self.player, self.session)
        else:
            embed = discord.Embed(
                title="❌ Craft Failed",
                description=result["message"],
                color=discord.Color.red(),
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red, emoji="❌")
    async def cancel_button(self, interaction: Interaction, button: discord.ui.Button):
        await self.session.adelete()
        await interaction.response.send_message("Crafting session cancelled.", ephemeral=True)


class CraftingCog(commands.GroupCog, name="craft"):
    """Session-based crafting system - add balls to session, then craft."""

    def __init__(self, bot: "BallsDexBot"):
        super().__init__()
        self.bot = bot

    async def _send_session_embed(
        self, interaction: Interaction | None, player: Player, session: CraftingSession
    ) -> discord.Embed:
        """Create and send the crafting session embed."""
        settings = await get_settings()
        items = await sync_to_async(list)(
            session.items.select_related("ball_instance__ball", "ball_instance__special").all()
        )

        # Count balls by type
        ball_counts: dict[str, int] = {}
        total_atk = 0
        total_hp = 0
        current_ingredients = []

        for item in items:
            ball = item.ball_instance.ball
            ball_name = ball.country
            ball_counts[ball_name] = ball_counts.get(ball_name, 0) + 1

            # Calculate stats
            atk_bonus = item.ball_instance.attack_bonus
            hp_bonus = item.ball_instance.health_bonus
            atk = ball.attack + int(ball.attack * atk_bonus * 0.01)
            hp = ball.health + int(ball.health * hp_bonus * 0.01)
            total_atk += atk
            total_hp += hp

            # Format instance display
            special_emoji = ""
            if item.ball_instance.special:
                special_emoji = f"{item.ball_instance.special.emoji} " if hasattr(item.ball_instance.special, 'emoji') else ""
            instance_str = f"{special_emoji}{item.ball_instance.short_description()} (ATK: {atk_bonus:+d}%, HP: {hp_bonus:+d}%)"
            current_ingredients.append(instance_str)

        # Find recipes that can be crafted
        all_recipes = await sync_to_async(list)(
            CraftingRecipe.objects.filter(enabled=True)
            .select_related("result_ball", "result_special")
            .prefetch_related("ingredients__ball")
        )

        craftable_recipes = []
        for recipe in all_recipes:
            ingredients = await sync_to_async(list)(recipe.ingredients.select_related("ball").all())
            can_craft = True
            for ingredient in ingredients:
                count = ball_counts.get(ingredient.ball.country, 0)
                if count < ingredient.quantity:
                    can_craft = False
                    break
            if can_craft:
                craftable_recipes.append(recipe)

        # Build embed
        embed = discord.Embed(
            title="🔨 Can Craft" if craftable_recipes else "❌ Cannot Craft",
            description="Add ingredients to see possible recipes. Use `/craft recipes` to view all available recipes.",
            color=discord.Color.green() if craftable_recipes else discord.Color.red(),
        )

        # Current ingredients
        if current_ingredients:
            ingredients_text = "\n".join(current_ingredients[:20])  # Limit to 20 for display
            if len(current_ingredients) > 20:
                ingredients_text += f"\n*(+{len(current_ingredients) - 20} more)*"
            embed.add_field(name="Current Ingredients", value=ingredients_text, inline=False)
        else:
            embed.add_field(name="Current Ingredients", value="None", inline=False)

        # Total stats
        if items:
            embed.add_field(
                name="Total Stats of all ingredients",
                value=f"ATK: {total_atk} | HP: {total_hp}",
                inline=False,
            )

        # Craftable recipes
        if craftable_recipes:
            recipe_names = [r.name for r in craftable_recipes[:10]]
            embed.add_field(
                name=f"Can Craft ({len(craftable_recipes)})",
                value=", ".join(recipe_names) or "None",
                inline=False,
            )

        # Session expiry
        time_left = (session.expires_at - timezone.now()).total_seconds()
        minutes_left = int(time_left / 60)
        embed.set_footer(text=f"Session expires in {minutes_left} minutes")

        # Commands help
        embed.add_field(
            name="Commands",
            value="`/craft add` - Add specific instance\n`/craft remove` - Remove specific instance\n`/craft clear` - Clear all ingredients\n`/craft recipes` - View available recipes",
            inline=False,
        )

        view = CraftView(self, player, session) if craftable_recipes else None

        if interaction:
            if interaction.response.is_done():
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            else:
                await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        else:
            return embed

        return embed

    async def _perform_craft_from_session(self, player: Player, session: CraftingSession) -> dict:
        """Perform craft using session ingredients."""
        settings = await get_settings()
        if not settings.enabled:
            return {"success": False, "message": "Crafting is currently disabled."}

        items = await sync_to_async(list)(
            session.items.select_related("ball_instance__ball").all()
        )

        # Count balls by type
        ball_counts: dict[str, int] = {}
        ball_instances: dict[str, list[BallInstance]] = {}
        for item in items:
            ball_name = item.ball_instance.ball.country
            ball_counts[ball_name] = ball_counts.get(ball_name, 0) + 1
            if ball_name not in ball_instances:
                ball_instances[ball_name] = []
            ball_instances[ball_name].append(item.ball_instance)

        # Find first craftable recipe
        all_recipes = await sync_to_async(list)(
            CraftingRecipe.objects.filter(enabled=True)
            .select_related("result_ball", "result_special")
            .prefetch_related("ingredients__ball")
        )

        recipe = None
        for r in all_recipes:
            ingredients = await sync_to_async(list)(r.ingredients.select_related("ball").all())
            can_craft = True
            for ingredient in ingredients:
                count = ball_counts.get(ingredient.ball.country, 0)
                if count < ingredient.quantity:
                    can_craft = False
                    break
            if can_craft:
                recipe = r
                break

        if not recipe:
            return {"success": False, "message": "No recipe can be crafted with current ingredients."}

        if not recipe.result_ball:
            return {"success": False, "message": "Recipe has no result configured."}

        # Get ingredients in sync context first
        ingredients = await sync_to_async(list)(recipe.ingredients.select_related("ball").all())

        # Consume ingredients and create result
        def perform_craft(ingredients_list):
            with transaction.atomic():
                # Delete consumed ball instances
                consumed_count = 0
                for ingredient in ingredients_list:
                    needed = ingredient.quantity
                    available = ball_instances.get(ingredient.ball.country, [])
                    for _ in range(min(needed, len(available))):
                        instance = available.pop(0)
                        instance.deleted = True
                        instance.save(update_fields=("deleted",))
                        consumed_count += 1

                # Create result
                created_ids = []
                for _ in range(recipe.result_quantity):
                    new_instance = BallInstance.objects.create(
                        ball=recipe.result_ball,
                        player=player,
                        special=recipe.result_special,
                        attack_bonus=0,
                        health_bonus=0,
                        spawned_time=timezone.now(),
                        catch_date=timezone.now(),
                    )
                    created_ids.append(new_instance.pk)

                # Delete session items that were consumed
                CraftingSessionItem.objects.filter(session=session).delete()

                return created_ids, consumed_count

        created_ids, consumed = await sync_to_async(perform_craft)(ingredients)

        ids_display = ", ".join(f"#{pk:0X}" for pk in created_ids)
        special_suffix = f" with {recipe.result_special.name}" if recipe.result_special else ""
        message = f"Crafted {recipe.result_quantity} × {recipe.result_ball.country}{special_suffix}\n**Pixels:** {ids_display}"

        return {"success": True, "message": message}

    # ----- Commands -----

    @app_commands.command(name="add", description="Add a specific ball instance to your crafting session.")
    @app_commands.describe(instance_id="The ID of the ball instance to add (e.g., #ABC123)")
    @app_commands.checks.bot_has_permissions(send_messages=True, embed_links=True)
    async def craft_add(self, interaction: Interaction, instance_id: str):
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Parse instance ID (remove # if present, convert hex to int)
        try:
            instance_id = instance_id.strip().lstrip("#")
            instance_pk = int(instance_id, 16)
        except ValueError:
            await interaction.followup.send("Invalid instance ID format. Use format like #ABC123", ephemeral=True)
            return

        player = await ensure_player(interaction.user)
        settings = await get_settings()

        if not settings.enabled:
            await interaction.followup.send("Crafting is currently disabled.", ephemeral=True)
            return

        # Get ball instance
        try:
            instance = await BallInstance.objects.select_related("ball", "special").aget(
                pk=instance_pk, player=player, deleted=False
            )
        except BallInstance.DoesNotExist:
            await interaction.followup.send("Ball instance not found or you don't own it.", ephemeral=True)
            return

        # Get or create session
        session = await get_or_create_session(player, settings)

        # Check if already added
        exists = await CraftingSessionItem.objects.filter(session=session, ball_instance=instance).aexists()
        if exists:
            await interaction.followup.send(f"{instance.short_description()} is already in your crafting session!", ephemeral=True)
            return

        # Add to session
        await CraftingSessionItem.objects.acreate(session=session, ball_instance=instance)

        await interaction.followup.send(f"Added {instance.short_description()} to crafting session!", ephemeral=True)

        # Refresh session view
        await self._send_session_embed(interaction, player, session)

    @app_commands.command(name="remove", description="Remove a specific ball instance from your crafting session.")
    @app_commands.describe(instance_id="The ID of the ball instance to remove (e.g., #ABC123)")
    @app_commands.checks.bot_has_permissions(send_messages=True, embed_links=True)
    async def craft_remove(self, interaction: Interaction, instance_id: str):
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Parse instance ID
        try:
            instance_id = instance_id.strip().lstrip("#")
            instance_pk = int(instance_id, 16)
        except ValueError:
            await interaction.followup.send("Invalid instance ID format. Use format like #ABC123", ephemeral=True)
            return

        player = await ensure_player(interaction.user)
        settings = await get_settings()

        if not settings.enabled:
            await interaction.followup.send("Crafting is currently disabled.", ephemeral=True)
            return

        # Get session
        try:
            session = await CraftingSession.objects.aget(player=player)
        except CraftingSession.DoesNotExist:
            await interaction.followup.send("You don't have an active crafting session.", ephemeral=True)
            return

        # Remove from session
        deleted = await CraftingSessionItem.objects.filter(session=session, ball_instance_id=instance_pk).adelete()
        if deleted[0] == 0:
            await interaction.followup.send("Ball instance not found in your crafting session.", ephemeral=True)
            return

        await interaction.followup.send("Removed ball instance from crafting session!", ephemeral=True)

        # Refresh session view
        await self._send_session_embed(interaction, player, session)

    @app_commands.command(name="clear", description="Clear all ingredients from your crafting session.")
    @app_commands.checks.bot_has_permissions(send_messages=True, embed_links=True)
    async def craft_clear(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        player = await ensure_player(interaction.user)
        settings = await get_settings()

        if not settings.enabled:
            await interaction.followup.send("Crafting is currently disabled.", ephemeral=True)
            return

        # Get session
        try:
            session = await CraftingSession.objects.aget(player=player)
        except CraftingSession.DoesNotExist:
            await interaction.followup.send("You don't have an active crafting session.", ephemeral=True)
            return

        # Clear session
        await CraftingSessionItem.objects.filter(session=session).adelete()
        await session.adelete()

        await interaction.followup.send("Cleared all ingredients from crafting session!", ephemeral=True)

    @app_commands.command(name="recipes", description="View all available crafting recipes.")
    @app_commands.checks.bot_has_permissions(send_messages=True, embed_links=True)
    async def craft_recipes(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)

        settings = await get_settings()
        if not settings.enabled:
            await interaction.followup.send("Crafting is currently disabled.", ephemeral=True)
            return

        recipes = await sync_to_async(list)(
            CraftingRecipe.objects.filter(enabled=True)
            .select_related("result_ball", "result_special")
            .prefetch_related("ingredients__ball")
        )

        if not recipes:
            await interaction.followup.send("No crafting recipes are available right now.", ephemeral=True)
            return

        embeds = []
        for recipe in recipes[:10]:
            ingredients = await sync_to_async(list)(recipe.ingredients.select_related("ball").all())
            ingredients_text = "\n".join(f"{i.quantity} × {i.ball.country}" for i in ingredients) or "None"

            embed = discord.Embed(
                title=recipe.name,
                description=recipe.description or "No description provided.",
            )

            embed.add_field(name="Ingredients", value=ingredients_text, inline=False)

            if recipe.result_ball:
                special = f" with {recipe.result_special.name}" if recipe.result_special else ""
                result = f"{recipe.result_quantity} × {recipe.result_ball.country}{special}"
                embed.add_field(name="Result", value=result, inline=False)

            embeds.append(embed)

        await interaction.followup.send(embeds=embeds, ephemeral=True)
