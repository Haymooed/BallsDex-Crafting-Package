from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
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


class CraftingItem(models.Model):
    """Custom crafting items managed by admins."""

    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Crafting Item"
        verbose_name_plural = "Crafting Items"
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class PlayerItemBalance(models.Model):
    """Tracks how many crafting items a player owns."""

    player = models.ForeignKey(Player, on_delete=models.CASCADE, related_name="crafting_items")
    item = models.ForeignKey(CraftingItem, on_delete=models.CASCADE, related_name="balances")
    quantity = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("player", "item")
        verbose_name = "Player Item Balance"
        verbose_name_plural = "Player Item Balances"

    def __str__(self) -> str:
        return f"{self.player_id} - {self.item.name} ({self.quantity})"


class CraftingRecipe(models.Model):
    """Crafting recipe definition."""

    RESULT_BALL = "ball"
    RESULT_ITEM = "item"
    RESULT_CHOICES = (
        (RESULT_BALL, "BallInstance"),
        (RESULT_ITEM, "Item"),
    )

    name = models.CharField(max_length=128, unique=True)
    description = models.TextField(blank=True)
    enabled = models.BooleanField(default=True, help_text="If disabled, players cannot view or craft this recipe.")
    allow_auto = models.BooleanField(default=True, help_text="Allow players to enable auto-crafting for this recipe.")
    cooldown_seconds = models.PositiveIntegerField(default=0, help_text="Extra cooldown applied after crafting this recipe.")
    result_type = models.CharField(max_length=16, choices=RESULT_CHOICES, default=RESULT_BALL)
    result_ball = models.ForeignKey(
        Ball,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Ball awarded when result_type is BallInstance.",
    )
    result_item = models.ForeignKey(
        CraftingItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Item granted when result_type is Item.",
        related_name="recipes",
    )
    result_quantity = models.PositiveIntegerField(default=1, help_text="Quantity of the result to grant.")
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

    def clean(self) -> None:
        """Validate result fields based on result_type."""
        errors: dict[str, list[str]] = {}
        if self.result_type == self.RESULT_BALL:
            if not self.result_ball:
                errors.setdefault("result_ball", []).append("Select a ball to grant for this recipe.")
        elif self.result_type == self.RESULT_ITEM:
            if not self.result_item:
                errors.setdefault("result_item", []).append("Select an item to grant for this recipe.")
        if self.result_quantity < 1:
            errors.setdefault("result_quantity", []).append("Quantity must be at least 1.")
        if errors:
            raise ValidationError(errors)


class CraftingIngredient(models.Model):
    """Ingredient required for a recipe."""

    INGREDIENT_BALL = "ball"
    INGREDIENT_ITEM = "item"
    INGREDIENT_CHOICES = (
        (INGREDIENT_BALL, "Ball"),
        (INGREDIENT_ITEM, "Item"),
    )

    recipe = models.ForeignKey(
        CraftingRecipe, on_delete=models.CASCADE, related_name="ingredients", help_text="Recipe this ingredient belongs to."
    )
    ingredient_type = models.CharField(max_length=16, choices=INGREDIENT_CHOICES)
    ball = models.ForeignKey(
        Ball,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Ball required when ingredient_type is Ball.",
        related_name="crafting_ingredients",
    )
    item = models.ForeignKey(
        CraftingItem,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Item required when ingredient_type is Item.",
        related_name="crafting_ingredients",
    )
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        verbose_name = "Crafting Ingredient"
        verbose_name_plural = "Crafting Ingredients"

    def __str__(self) -> str:
        target = self.ball or self.item
        return f"{self.quantity} x {target} ({self.get_ingredient_type_display()})"

    def clean(self) -> None:
        errors: dict[str, list[str]] = {}
        if self.quantity < 1:
            errors.setdefault("quantity", []).append("Quantity must be at least 1.")
        if self.ingredient_type == self.INGREDIENT_BALL:
            if not self.ball:
                errors.setdefault("ball", []).append("Select a ball for this ingredient.")
            if self.item:
                errors.setdefault("item", []).append("Remove the item when using a ball ingredient.")
        elif self.ingredient_type == self.INGREDIENT_ITEM:
            if not self.item:
                errors.setdefault("item", []).append("Select an item for this ingredient.")
            if self.ball:
                errors.setdefault("ball", []).append("Remove the ball when using an item ingredient.")
        if errors:
            raise ValidationError(errors)


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

