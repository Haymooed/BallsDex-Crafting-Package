from django.apps import AppConfig


class CraftingConfig(AppConfig):
    """Django app configuration for the crafting package."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "crafting"
    verbose_name = "Crafting"
    dpy_package = "crafting.package"  # Path to the discord.py extension

