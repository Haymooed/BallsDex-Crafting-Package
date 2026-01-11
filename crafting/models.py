from __future__ import annotations

from django.db import models
from django.utils import timezone

from bd_models.models import Ball, BallInstance, Player, Special


class CraftingSettings(models.Model):
    """Singleton configuration for crafting behaviour."""

    enabled = models.BooleanField(default=True, help_text="Globally enable crafting commands")
    global_cooldown_seconds = models.PositiveIntegerField(
        default=10,
        help_text="Global cooldown (in seconds) applied after any craft",
    )
    allow_auto_crafting = models.BooleanField(
        default=False, help_text="Allow players to enable auto-crafting loops per recipe"
    )

    class Meta:
        verbose_name = "Crafting Settings"

    def __str__(self) -> str:
        return "Crafting Settings"

    @classmethod
    def get_solo(cls) -> "CraftingSettings":
        """
        Lightweight replacement for django-solo's get_solo().

        Ensures there is always exactly one settings row.
        """
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class CraftingRecipe(models.Model):
    """Simple crafting recipe - combine balls to get a new ball."""

    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True, help_text="If disabled, players cannot view or craft this recipe.")
    allow_auto = models.BooleanField(default=True, help_text="Allow players to enable auto-crafting for this recipe.")
    cooldown_seconds = models.PositiveIntegerField(
        default=0, help_text="Extra cooldown applied after crafting this recipe."
    )

    # Result - always a ball
    result_ball = models.ForeignKey(
        Ball,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Ball awarded when recipe is crafted.",
    )
    result_quantity = models.PositiveIntegerField(default=1, help_text="Quantity of balls to grant.")
    result_special = models.ForeignKey(
        Special,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Optional special applied to crafted BallInstances.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Crafting Recipe"
        verbose_name_plural = "Crafting Recipes"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class CraftingIngredient(models.Model):
    """Ball ingredient required for a recipe."""

    recipe = models.ForeignKey(
        CraftingRecipe, on_delete=models.CASCADE, related_name="ingredients", help_text="Recipe this ingredient belongs to."
    )
    ball = models.ForeignKey(
        Ball,
        on_delete=models.CASCADE,
        help_text="Ball required for this recipe.",
        related_name="crafting_ingredients",
    )
    quantity = models.PositiveIntegerField(default=1, help_text="How many of this ball are needed.")

    class Meta:
        verbose_name = "Crafting Ingredient"
        verbose_name_plural = "Crafting Ingredients"

    def __str__(self) -> str:
        return f"{self.quantity} x {self.ball.country}"


class CraftingProfile(models.Model):
    """Per-player crafting metadata such as cooldown tracking."""

    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name="crafting_profile")
    last_crafted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Crafting Profile"
        verbose_name_plural = "Crafting Profiles"

    def __str__(self) -> str:
        return f"Profile for {self.player_id}"

    def update_cooldown(self) -> None:
        self.last_crafted_at = timezone.now()


class CraftingRecipeState(models.Model):
    """Per-player state for a recipe (cooldown and auto flag)."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="crafting_states")
    recipe = models.ForeignKey(CraftingRecipe, on_delete=models.CASCADE, related_name="states")
    last_crafted_at = models.DateTimeField(null=True, blank=True)
    auto_enabled = models.BooleanField(default=False)

    class Meta:
        unique_together = ("player", "recipe")
        verbose_name = "Crafting Recipe State"
        verbose_name_plural = "Crafting Recipe States"

    def __str__(self) -> str:
        return f"State for {self.player_id} / {self.recipe.name}"

    def update_cooldown(self) -> None:
        self.last_crafted_at = timezone.now()


class CraftingLog(models.Model):
    """Audit log of crafting attempts."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="crafting_logs")
    recipe = models.ForeignKey(CraftingRecipe, on_delete=models.CASCADE, related_name="logs")
    success = models.BooleanField(default=True)
    message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Crafting Log"
        verbose_name_plural = "Crafting Logs"
        ordering = ("-created_at",)

    def __str__(self) -> str:
        status = "Success" if self.success else "Failure"
        return f"{status}: {self.recipe.name} for player {self.player_id}"
