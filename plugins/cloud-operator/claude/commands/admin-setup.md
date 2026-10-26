---
description: One-time Cloud Operator (AutoCloud) organization admin setup - checks each step and asks before every change. Pass "status" to only check.
argument-hint: "[status]"
---

Read `${CLAUDE_PLUGIN_ROOT}/skills/admin-setup/SKILL.md` and follow it exactly. In that file, `<SKILL_DIR>` is `${CLAUDE_PLUGIN_ROOT}/skills/admin-setup`.

Arguments: `$ARGUMENTS`. If it's `status`, run only the status check described there.

When a step needs the admin to sign in to gcloud (`gcloud auth login <account>`), ask them to run it themselves with the `!` prefix (for example `! gcloud auth login <account>`) and wait for them.
