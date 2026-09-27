# The Skill Contract

## Contents

- [What a skill is](#what-a-skill-is)
- [Frontmatter fields](#frontmatter-fields)
- [Validation rules](#validation-rules)
- [Discovery: where skills live](#discovery-where-skills-live)
- [How a skill reaches the model](#how-a-skill-reaches-the-model)
- [Silent failure modes](#silent-failure-modes)
- [Invocation policy](#invocation-policy)
- [Installing and sharing](#installing-and-sharing)
- [Portability to other hosts](#portability-to-other-hosts)

## What a skill is

A skill is a directory containing at minimum a `SKILL.md`:

```
skill-name/
├── SKILL.md          # Required: frontmatter + instructions
├── references/       # Optional: documentation, read on demand
├── scripts/          # Optional: executable code, run without being read
├── assets/           # Optional: templates, fonts, static files
└── ...               # Any additional files
```

The `SKILL.md` file is YAML frontmatter followed by a Markdown body. Anything else in the directory is inert until the agent chooses to open or run it.

## Frontmatter fields

```yaml
---
name: writing-skills
description: What it does and when to use it.
whenToUse: An extra hint about the triggering situation.
metadata:
  version: "1.0"
  author: example-org
disable-model-invocation: false
user-invocable: true
---
```

| Field | Required | Type | Notes |
|---|---|---|---|
| `name` | Yes | string | Kebab-case, see regex below. Should equal the directory or file name |
| `description` | Yes | string | Non-empty. Capability + triggers. Keep under 500 characters |
| `whenToUse` | No | string | camelCase. Extra triggering context |
| `metadata` | No | map | Arbitrary string keys and values. Use unique keys |
| `disable-model-invocation` | No | boolean | kebab-case. `true` hides it from the model catalog |
| `user-invocable` | No | boolean | kebab-case. `false` hides it from `/name` commands |
| `license` | No | string | Portable to other hosts; ignored by DSH |
| `compatibility` | No | string | Portable to other hosts; ignored by DSH |
| `allowed-tools` | No | string | Portable to other hosts; ignored by DSH |

Omitted invocation fields default to permitting their surface.

## Validation rules

Enforced at discovery time. A violation drops the skill.

| Rule | Detail |
|---|---|
| Name pattern | `/^[a-z0-9]+(?:-[a-z0-9]+)*$/` — lowercase letters, digits, single hyphens between segments. No leading, trailing, or doubled hyphens, no underscores, no uppercase |
| Name length | 1–64 characters in the portable spec; keep it short regardless |
| Description | Required, non-empty, and the first field the model ever sees |
| Booleans | YAML booleans, plus case-insensitive `true`/`false`, `yes`/`no`, `on`/`off`, `1`/`0`. Anything else is rejected |
| Rejected keys | `disableModelInvocation`, `modelInvocable`, `userInvocable` — these fail loudly and drop the skill |

The rejected-key rule is the sharpest edge in the format. The camelCase invocation spellings were superseded by the kebab-case ones, and the parser does not quietly accept them: it throws, the file is skipped, and the model is told nothing.

## Discovery: where skills live

Roots are scanned in rank order. A nearer root wins a duplicate name outright.

| Rank | Source | Path |
|---|---|---|
| 100 | `project-dsh` | `<projectRoot>/.dsh/skills` |
| 200 | `project-agents` | `<projectRoot>/.agents/skills` |
| 300 | `custom` | configured `customSkillDirs` |
| 400 | `user-dsh` | `<dshHome>/skills` (default `~/.dsh/skills`) |
| 500 | `user-agents` | `<agentsHome>/skills` (default `~/.agents/skills`) |
| 600 | `bundled` | configured `bundledSkillDir` |

`<projectRoot>` is the nearest ancestor containing `.git`. Without one, the current working directory is the project root.

**Discovery is exactly one level deep.** Only these two shapes are recognized:

```
<root>/<name>/SKILL.md      ✅ directory bundle
<root>/<name>.md            ✅ flat file
<root>/<name>/sub/SKILL.md  ❌ not discovered
```

A `.system` child of the user DSH root is skipped.

## How a skill reaches the model

1. **Catalog.** Before the first request, the agent receives a durable message listing every model-invocable skill's `name` and a capped `description`. The cap defaults to 500 characters, configurable via `catalogDescriptionMaxLength` (minimum 3). Anything past the cap is truncated — front-load the decisive words.
2. **Load.** The agent calls the `skill` tool with the exact kebab-case name and receives the full body plus resource guidance, wrapped in a canonical `<skill_content>` block retained as ordinary tool history.
3. **User invocation.** A `/name` token in direct user input injects that skill's instructions for the step, provided the skill is user-invocable.

Errors are explicit on this path: an invalid name reports `invalid skill name`, an unknown name reports the skill is unknown or no longer available, and a model-disabled skill reports it is unavailable for model invocation.

The catalog is live. Adding, renaming, or deleting a skill — or editing its frontmatter — appends a replacement catalog on the next step, with no restart. Editing files *below* `references/`, `scripts/`, and `assets/` does not trigger a refresh, but every load re-reads the current body from disk, so body edits always take effect on the next load.

## Silent failure modes

These produce no message to the model. The skill is simply absent, which looks exactly like a skill that never triggered.

| Cause | Symptom |
|---|---|
| `whenToUse` written as `when-to-use` | Field ignored; no error |
| Legacy camelCase invocation key | Skill dropped with a host warning |
| Missing `description` | Skill dropped with a host warning |
| `name` violates the regex (uppercase, underscore, `--`) | Skill dropped with a host warning |
| Skill nested more than one level below the root | Never discovered |
| Frontmatter not at the very top of the file, or unterminated `---` | Parsed as no frontmatter, skill dropped |
| Name mismatched from the directory name | Loads, but the catalog and the path disagree — confusing to maintain |
| Description over the catalog cap | Loads, but the tail is invisible during selection |

Because the model cannot distinguish "absent" from "invalid", run the bundled validator whenever a skill fails to appear:

```bash
python scripts/validate_skill.py <skill-directory>
```

## Invocation policy

Two independent switches decide which surfaces may advertise and load a skill.

| `disable-model-invocation` | `user-invocable` | Model catalog | `/name` command |
|---|---|---|---|
| `false` (default) | `true` (default) | included | included |
| `true` | `true` | excluded | included |
| `false` | `false` | included | excluded |
| `true` | `false` | excluded | excluded |

Use `disable-model-invocation: true` for a skill that should only run when a human explicitly asks for it — a destructive maintenance routine, for instance, which the model should never reach for on its own.

## Installing and sharing

A skill is installed by placing its directory under any scanned root. No build step, manifest, or registry is involved.

- **This project only** — `<projectRoot>/.dsh/skills/<name>/`. Commit it with the repository.
- **This machine, every project** — `~/.dsh/skills/<name>/`.
- **Shared with other agent tooling** — `~/.agents/skills/<name>/`.

To share a skill, copy the directory; the whole directory is the unit. Keep it self-contained and audit third-party skills before installing them: a skill can carry executable scripts, and its instructions run with the agent's authority.

## Portability to other hosts

The format is an open standard, and this skill's guidance applies across hosts. Two differences are worth knowing when moving a skill between them:

- **Frontmatter.** `whenToUse`, `disable-model-invocation`, and `user-invocable` are DSH extensions, ignored elsewhere. The portable field set is `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`.
- **Optional directories.** Other hosts and the portable spec reserve `scripts/`, `references/`, and `assets/` for executable code, on-demand docs, and output assets respectively. Using those names keeps a skill portable.
