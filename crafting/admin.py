from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin
from solo.admin import SingletonModelAdmin

from .models import (
    CraftingIngredient,
    CraftingItem,
    CraftingLog,
    CraftingProfile,
    CraftingRecipe,
    CraftingRecipeState,
    CraftingSettings,
    PlayerItemBalance,
)

if TYPE_CHECKING:
    from django.db.models import QuerySet


@admin.register(CraftingSettings)
class CraftingSettingsAdmin(SingletonModelAdmin):
    """Singleton admin for crafting settings."""

    fieldsets = (
        (
            "Status",
            {"fields": ("enabled",)},
        ),
        (
            "Behaviour",
            {
                "fields": (
                    "global_cooldown_seconds",
                    "allow_auto_crafting",
                ),
            },
        ),
    )


@admin.register(CraftingItem)
class CraftingItemAdmin(admin.ModelAdmin):
    """Admin configuration for crafting items."""

    list_display = ("name", "enabled")
    list_filter = ("enabled",)
    search_fields = ("name", "description")


@admin.register(PlayerItemBalance)
class PlayerItemBalanceAdmin(admin.ModelAdmin):
    """Admin for player item balances."""

    list_display = ("player", "item", "quantity")
    search_fields = ("player__discord_id", "item__name")
    list_filter = ("item",)


class CraftingIngredientInline(admin.TabularInline):
    """Inline ingredient editor for recipes."""

    model = CraftingIngredient
    extra = 1


@admin.register(CraftingRecipe)
class CraftingRecipeAdmin(admin.ModelAdmin):
    """Admin configuration for crafting recipes."""

    list_display = ("name", "enabled", "allow_auto", "result_summary", "cooldown_seconds", "updated_at")
    list_filter = ("enabled", "allow_auto", "result_type")
    search_fields = ("name", "description")
    inlines = (CraftingIngredientInline,)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (
            "Recipe Info",
            {"fields": ("name", "description", "enabled", "allow_auto", "cooldown_seconds")},
        ),
        (
            "Result",
            {
                "fields": (
                    "result_type",
                    "result_ball",
                    "result_special",
                    "result_item",
                    "result_quantity",
                )
            },
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    @admin.display(description="Result")
    def result_summary(self, obj: CraftingRecipe) -> str:
        """Human readable result description."""
        if obj.result_type == CraftingRecipe.RESULT_BALL:
            return f"{obj.result_quantity} × {obj.result_ball} (Special: {obj.result_special or 'None'})"
        return f"{obj.result_quantity} × {obj.result_item}"


@admin.register(CraftingProfile)
class CraftingProfileAdmin(admin.ModelAdmin):
    """Admin for crafting profiles."""

    list_display = ("player", "last_crafted_at")
    search_fields = ("player__discord_id",)


@admin.register(CraftingRecipeState)
class CraftingRecipeStateAdmin(admin.ModelAdmin):
    """Admin for per-recipe player state."""

    list_display = ("player", "recipe", "auto_enabled", "last_crafted_at")
    list_filter = ("auto_enabled",)
    search_fields = ("player__discord_id", "recipe__name")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("player", "recipe")


@admin.register(CraftingLog)
class CraftingLogAdmin(admin.ModelAdmin):
    """Read-only audit log for crafting attempts."""

    list_display = ("created_at", "player", "recipe", "success")
    list_filter = ("success", "recipe")
    search_fields = ("player__discord_id", "recipe__name", "message")
    readonly_fields = ("player", "recipe", "success", "message", "created_at")

    def has_add_permission(self, request):
        return False

