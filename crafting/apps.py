from django.apps import AppConfig


class CraftingConfig(AppConfig):
    name = "crafting"
    label = "crafting"  # avoid conflicts
    verbose_name = "BallsDex Crafting"
    dpy_package = "crafting.package"
    default_auto_field = "django.db.models.BigAutoField"