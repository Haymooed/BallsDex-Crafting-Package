from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("crafting", "0001_initial"),
        ("bd_models", "0001_initial"),
    ]

    operations = [
        # Update CraftingIngredient first - remove item field before deleting CraftingItem
        migrations.RemoveField(
            model_name="craftingingredient",
            name="item",
        ),
        migrations.RemoveField(
            model_name="craftingingredient",
            name="ingredient_type",
        ),
        # Update CraftingRecipe - remove result_item before deleting CraftingItem
        migrations.RemoveField(
            model_name="craftingrecipe",
            name="result_item",
        ),
        migrations.RemoveField(
            model_name="craftingrecipe",
            name="result_type",
        ),
        migrations.RemoveField(
            model_name="craftingrecipe",
            name="allow_auto",
        ),
        migrations.RemoveField(
            model_name="craftingrecipe",
            name="cooldown_seconds",
        ),
        # Now delete tables that depend on CraftingItem
        migrations.DeleteModel(
            name="PlayerItemBalance",
        ),
        migrations.DeleteModel(
            name="CraftingItem",
        ),
        # Delete other old tables
        migrations.DeleteModel(
            name="CraftingLog",
        ),
        migrations.DeleteModel(
            name="CraftingRecipeState",
        ),
        migrations.DeleteModel(
            name="CraftingProfile",
        ),
        # Update CraftingSettings - remove old fields, add new
        migrations.RemoveField(
            model_name="craftingsettings",
            name="allow_auto_crafting",
        ),
        migrations.RemoveField(
            model_name="craftingsettings",
            name="global_cooldown_seconds",
        ),
        migrations.AddField(
            model_name="craftingsettings",
            name="session_timeout_minutes",
            field=models.PositiveIntegerField(
                default=10, help_text="How long crafting sessions last before expiring"
            ),
        ),
        # Delete all existing ingredients (they may have NULL balls)
        migrations.RunSQL(
            "DELETE FROM crafting_craftingingredient WHERE ball_id IS NULL;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        # Make CraftingIngredient.ball non-nullable (after removing item and deleting old data)
        migrations.AlterField(
            model_name="craftingingredient",
            name="ball",
            field=models.ForeignKey(
                help_text="Ball required for this recipe.",
                on_delete=django.db.models.deletion.CASCADE,
                related_name="crafting_ingredients",
                to="bd_models.ball",
            ),
        ),
        # Create new session tables
        migrations.CreateModel(
            name="CraftingSession",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                (
                    "player",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="crafting_session",
                        to="bd_models.player",
                    ),
                ),
            ],
            options={
                "verbose_name": "Crafting Session",
                "verbose_name_plural": "Crafting Sessions",
            },
        ),
        migrations.CreateModel(
            name="CraftingSessionItem",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True, primary_key=True, serialize=False, verbose_name="ID"
                    ),
                ),
                (
                    "ball_instance",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, to="bd_models.ballinstance"
                    ),
                ),
                (
                    "session",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="items",
                        to="crafting.craftingsession",
                    ),
                ),
            ],
            options={
                "verbose_name": "Crafting Session Item",
                "verbose_name_plural": "Crafting Session Items",
                "unique_together": {("session", "ball_instance")},
            },
        ),
    ]
