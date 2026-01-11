from __future__ import annotations

from django.db import models
from django.utils import timezone

from bd_models.models import Ball, BallInstance, Player, Special


class CraftingSettings(models.Model):
    """Singleton configuration for crafting behaviour."""

    enabled = models.BooleanField(default=True, help_text="Globally enable crafting commands")
    session_timeout_minutes = models.PositiveIntegerField(
        default=10, help_text="How long crafting sessions last before expiring"
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
    enabled = models.BooleanField(default=True, help_text="If disabled, players cannot craft this recipe.")

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


class CraftingSession(models.Model):
    """Player's active crafting session with added ball instances."""

    player = models.OneToOneField(Player, on_delete=models.CASCADE, related_name="crafting_session")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        verbose_name = "Crafting Session"
        verbose_name_plural = "Crafting Sessions"

    def __str__(self) -> str:
        return f"Session for {self.player_id}"

    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at


class CraftingSessionItem(models.Model):
    """Ball instance added to a crafting session."""

    session = models.ForeignKey(CraftingSession, on_delete=models.CASCADE, related_name="items")
    ball_instance = models.ForeignKey(BallInstance, on_delete=models.CASCADE)

    class Meta:
        verbose_name = "Crafting Session Item"
        verbose_name_plural = "Crafting Session Items"
        unique_together = ("session", "ball_instance")

    def __str__(self) -> str:
        return f"{self.ball_instance} in session {self.session_id}"
