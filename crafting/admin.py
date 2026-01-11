from __future__ import annotations

from typing import TYPE_CHECKING

from django.contrib import admin

from .models import (
    CraftingIngredient,
    CraftingRecipe,
    CraftingSession,
    CraftingSessionItem,
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
                "fields": ("session_timeout_minutes",),
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

    list_display = ("name", "enabled", "result_summary", "updated_at")
    list_filter = ("enabled",)
    search_fields = ("name", "description")
    inlines = (CraftingIngredientInline,)
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("result_ball", "result_special")

    fieldsets = (
        (
            "Recipe Info",
            {"fields": ("name", "description", "enabled")},
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


class CraftingSessionItemInline(admin.TabularInline):
    """Inline items for crafting sessions."""

    model = CraftingSessionItem
    extra = 0
    fields = ("ball_instance",)
    autocomplete_fields = ("ball_instance",)
    readonly_fields = ("ball_instance",)


@admin.register(CraftingSession)
class CraftingSessionAdmin(admin.ModelAdmin):
    """Admin for crafting sessions."""

    list_display = ("player", "created_at", "expires_at", "is_expired_display")
    search_fields = ("player__discord_id",)
    autocomplete_fields = ("player",)
    inlines = (CraftingSessionItemInline,)
    readonly_fields = ("created_at", "expires_at")

    @admin.display(description="Expired")
    def is_expired_display(self, obj: CraftingSession) -> str:
        return "Yes" if obj.is_expired() else "No"
