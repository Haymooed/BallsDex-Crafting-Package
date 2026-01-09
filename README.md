# BallsDex V3 Crafting Package 🛠️

The **Crafting Package** for **BallsDex V3** allows players to combine items and materials to create new collectibles. The system is fully configurable via the **admin panel** and follows the **same structure and conventions** as the BallsDex V3 Merchant Package.

This package is designed to integrate cleanly with the BallsDex V3 custom package system.

---

## Installation (`extra.toml`)

Add the following entry to `config/extra.toml` so BallsDex installs the package automatically:

```toml
[[ballsdex.packages]]
location = "git+https://github.com/Haymooed/BallsDex-Crafting-Package.git"
path = "crafting"
enabled = true
editable = false
```

The package is distributed as a standard Python package — no manual file copying required.

---

## Admin Panel Integration

The crafting system works entirely through the admin panel, following the same format and patterns used by the BallsDex V3 Merchant Package.

No values are hardcoded. All settings and data are editable from the panel.

### Configuration

Configuration follows the BallsDex V3 custom package guidelines:
https://wiki.ballsdex.com/dev/custom-package/

#### Crafting Settings (singleton)
- Enable / disable crafting
- Global craft cooldown (seconds)
- Auto-crafting toggle

#### Crafting Recipes
- Recipe name & description
- Enabled toggle and per-recipe cooldown
- Required ingredients (balls and/or custom items) with quantities
- Result (BallInstance with optional Special, or custom item + quantity)
- Per-recipe auto-crafting toggle

All crafting attempts are logged for moderation and auditing.

---

## Commands (Slash Commands / app_commands)

### Player Commands

- `/craft view` — View all available crafting recipes.
- `/craft craft <recipe>` — Craft the selected recipe if requirements are met.
- `/craft auto <recipe|off>` — Automatically craft the recipe whenever possible (until disabled). Use `off/0` to disable.

---

## Behaviour Requirements

- Recipes are only available when crafting is enabled.
- Crafting validates all requirements before execution.
- Auto-crafting respects cooldowns and resource availability.
- Ingredients are consumed only on successful crafts.
- All crafting attempts are logged for auditing.

---

## Technical Notes

- Follows the same file structure, setup flow, and patterns as the Merchant Package.
- Uses async `setup(bot)` and modern `app_commands`.
- Fully compatible with BallsDex V3 models (Ball, BallInstance, Player, Special).
- Designed to plug directly into the BallsDex V3 extra/custom package loader.

This package feels native to BallsDex V3, consistent with existing official and community packages, and easy for admins to manage through the panel.

---

## License

MIT License
