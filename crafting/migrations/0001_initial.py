from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("bd_models", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CraftingSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "enabled",
                    models.BooleanField(default=True, help_text="Globally enable crafting commands"),
                ),
                (
                    "global_cooldown_seconds",
                    models.PositiveIntegerField(
                        default=10, help_text="Global cooldown (in seconds) applied after any craft"
                    ),
                ),
                (
                    "allow_auto_crafting",
                    models.BooleanField(
                        default=False, help_text="Allow players to enable auto-crafting loops per recipe"
                    ),
                ),
            ],
            options={
                "verbose_name": "Crafting Settings",
            },
        ),
        migrations.CreateModel(
            name="CraftingItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128, unique=True)),
                ("description", models.TextField(blank=True)),
                ("enabled", models.BooleanField(default=True)),
            ],
            options={
                "verbose_name": "Crafting Item",
                "verbose_name_plural": "Crafting Items",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="CraftingRecipe",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=128, unique=True)),
                ("description", models.TextField(blank=True)),
                (
                    "enabled",
                    models.BooleanField(
                        default=True, help_text="If disabled, players cannot view or craft this recipe."
                    ),
                ),
                (
                    "allow_auto",
                    models.BooleanField(
                        default=True, help_text="Allow players to enable auto-crafting for this recipe."
                    ),
                ),
                (
                    "cooldown_seconds",
                    models.PositiveIntegerField(
                        default=0, help_text="Extra cooldown applied after crafting this recipe."
                    ),
                ),
                (
                    "result_type",
                    models.CharField(
                        choices=[("ball", "BallInstance"), ("item", "Item")], default="ball", max_length=16
                    ),
                ),
                (
                    "result_quantity",
                    models.PositiveIntegerField(default=1, help_text="Quantity of the result to grant."),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "result_ball",
                    models.ForeignKey(
                        blank=True,
                        help_text="Ball awarded when result_type is BallInstance.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="bd_models.ball",
                    ),
                ),
                (
                    "result_item",
                    models.ForeignKey(
                        blank=True,
                        help_text="Item granted when result_type is Item.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="recipes",
                        to="crafting.craftingitem",
                    ),
                ),
                (
                    "result_special",
                    models.ForeignKey(
                        blank=True,
                        help_text="Optional special applied to crafted BallInstances.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        to="bd_models.special",
                    ),
                ),
            ],
            options={
                "verbose_name": "Crafting Recipe",
                "verbose_name_plural": "Crafting Recipes",
                "ordering": ("name",),
            },
        ),
        migrations.CreateModel(
            name="CraftingProfile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_crafted_at", models.DateTimeField(blank=True, null=True)),
                (
                    "player",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crafting_profile",
                        to="bd_models.player",
                    ),
                ),
            ],
            options={
                "verbose_name": "Crafting Profile",
                "verbose_name_plural": "Crafting Profiles",
            },
        ),
        migrations.CreateModel(
            name="CraftingRecipeState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("last_crafted_at", models.DateTimeField(blank=True, null=True)),
                ("auto_enabled", models.BooleanField(default=False)),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crafting_states",
                        to="bd_models.player",
                    ),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="states",
                        to="crafting.craftingrecipe",
                    ),
                ),
            ],
            options={
                "verbose_name": "Crafting Recipe State",
                "verbose_name_plural": "Crafting Recipe States",
                "unique_together": {("player", "recipe")},
            },
        ),
        migrations.CreateModel(
            name="CraftingLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("success", models.BooleanField(default=True)),
                ("message", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crafting_logs",
                        to="bd_models.player",
                    ),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="logs",
                        to="crafting.craftingrecipe",
                    ),
                ),
            ],
            options={
                "verbose_name": "Crafting Log",
                "verbose_name_plural": "Crafting Logs",
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="PlayerItemBalance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity", models.PositiveIntegerField(default=0)),
                (
                    "item",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="balances",
                        to="crafting.craftingitem",
                    ),
                ),
                (
                    "player",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crafting_items",
                        to="bd_models.player",
                    ),
                ),
            ],
            options={
                "verbose_name": "Player Item Balance",
                "verbose_name_plural": "Player Item Balances",
                "unique_together": {("player", "item")},
            },
        ),
        migrations.CreateModel(
            name="CraftingIngredient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("ingredient_type", models.CharField(choices=[("ball", "Ball"), ("item", "Item")], max_length=16)),
                ("quantity", models.PositiveIntegerField(default=1)),
                (
                    "ball",
                    models.ForeignKey(
                        blank=True,
                        help_text="Ball required when ingredient_type is Ball.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crafting_ingredients",
                        to="bd_models.ball",
                    ),
                ),
                (
                    "item",
                    models.ForeignKey(
                        blank=True,
                        help_text="Item required when ingredient_type is Item.",
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crafting_ingredients",
                        to="crafting.craftingitem",
                    ),
                ),
                (
                    "recipe",
                    models.ForeignKey(
                        help_text="Recipe this ingredient belongs to.",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="ingredients",
                        to="crafting.craftingrecipe",
                    ),
                ),
            ],
            options={
                "verbose_name": "Crafting Ingredient",
                "verbose_name_plural": "Crafting Ingredients",
            },
        ),
    ]

