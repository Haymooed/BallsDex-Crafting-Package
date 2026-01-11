from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from .models import (
    CraftingIngredient,
    CraftingLog,
    CraftingProfile,
    CraftingRecipe,
    CraftingRecipeState,
    CraftingSettings,
)

if TYPE_CHECKING:
    from django.db.models import QuerySet


@admin.register(CraftingSettings)
class CraftingSettingsAdmin(admin.ModelAdmin):
    """Singleton-style admin for crafting settings."""

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

    def has_add_permission(self, request):
        # Only allow a single settings row
        if CraftingSettings.objects.exists():
            return False
        return super().has_add_permission(request)


class CraftingIngredientInline(admin.TabularInline):
    """Inline ingredient editor for recipes."""

    model = CraftingIngredient
    extra = 1
    fields = ("ball", "quantity")
    autocomplete_fields = ("ball",)


@admin.register(CraftingRecipe)
class CraftingRecipeAdmin(admin.ModelAdmin):
    """Admin configuration for crafting recipes."""

    list_display = ("name", "enabled", "allow_auto", "result_summary", "cooldown_seconds", "updated_at")
    list_filter = ("enabled", "allow_auto")
    search_fields = ("name", "description")
    inlines = (CraftingIngredientInline,)
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("result_ball", "result_special")

    fieldsets = (
        (
            "Recipe Info",
            {"fields": ("name", "description", "enabled", "allow_auto", "cooldown_seconds")},
        ),
        (
            "Result",
            {
                "fields": (
                    "result_ball",
                    "result_special",
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
        if obj.result_ball:
            special = f" ({obj.result_special.name})" if obj.result_special else ""
            return f"{obj.result_quantity} × {obj.result_ball.country}{special}"
        return "No result configured"


@admin.register(CraftingProfile)
class CraftingProfileAdmin(admin.ModelAdmin):
    """Admin for crafting profiles."""

    list_display = ("player", "last_crafted_at")
    search_fields = ("player__discord_id",)
    autocomplete_fields = ("player",)


@admin.register(CraftingRecipeState)
class CraftingRecipeStateAdmin(admin.ModelAdmin):
    """Admin for per-recipe player state."""

    list_display = ("player", "recipe", "auto_enabled", "last_crafted_at")
    list_filter = ("auto_enabled",)
    search_fields = ("player__discord_id", "recipe__name")
    autocomplete_fields = ("player", "recipe")

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("player", "recipe")


@admin.register(CraftingLog)
class CraftingLogAdmin(admin.ModelAdmin):
    """Read-only audit log for crafting attempts."""

    list_display = ("created_at", "player", "recipe", "success")
    list_filter = ("success", "recipe")
    search_fields = ("player__discord_id", "recipe__name", "message")
    readonly_fields = ("player", "recipe", "success", "message", "created_at")
    autocomplete_fields = ("player", "recipe")

    def has_add_permission(self, request):
        return False
