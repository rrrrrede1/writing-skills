---
name: writing-skills
description: Author or revise an agent skill (SKILL.md). Covers choosing a trigger description, structuring the body, splitting detail into references/ and scripts/, and validating against the skill contract. Use when the user wants to create a skill, turn a repeated workflow into a skill, fix a skill that never triggers or is silently ignored, restructure an oversized SKILL.md, or debug skill frontmatter.
whenToUse: The user asks to create, write, edit, review, split, package, or debug a skill — a SKILL.md file, a skill folder, skill frontmatter, or a skill that is not triggering.
metadata:
  version: "1.0"
  applies-to: dsh
---

# Writing Skills

A skill is a directory containing `SKILL.md`: the frontmatter decides *when* the skill loads, the body decides *how* the job gets done. Treat the description as the product. A skill that never triggers is dead weight, and one that triggers on the wrong task burns context every session.

## The loop

```
Skill progress:
- [ ] 1. Pin the job
- [ ] 2. Write the description first
- [ ] 3. Draft SKILL.md
- [ ] 4. Split detail out as the body grows
- [ ] 5. Validate, then test on real prompts
```

Work in order. Skipping step 2 is the most common reason a skill never fires.

## 1. Pin the job

Get three answers before writing anything:

| Question | Why it decides the design |
|---|---|
| What should the agent do afterwards that it cannot do now? | A skill supplies knowledge the model lacks, not general competence |
| What will the user actually type when they need this? | Those phrasings become the description and the test prompts |
| What does a correct result look like? | Verifiable output warrants evaluations; taste-based output needs judgement |

Then check that a skill is the right container. A skill earns its place when the knowledge is reusable across sessions, specific to this user or team, and not something the model already does reliably. For a one-off task, just do the task. For "how this repository works", project documentation beats a skill.

If the conversation already contains the workflow — "turn what we just did into a skill" — mine it first for the tools used, the step order, the corrections the user made, and the output format. Confirm your reading rather than interrogating them from scratch.

## 2. Write the description first

The description is the entire triggering mechanism. The agent sees only each skill's `name` and `description` before deciding what to load, so every "when to use this" fact belongs there, not buried in the body.

Build it from three parts:

1. **Capability** — what the skill does, opening with a verb.
2. **Triggers** — the words, file types, and situations a user would actually write.
3. **Boundary** — what it deliberately does not cover, when that could be confused.

Write it before the body, because a description you cannot write crisply means the skill's scope is still fuzzy.

Two constraints worth respecting:

- **Stay under 500 characters.** Hosts cap the catalog rendering (DSH defaults to 500), so a longer description is silently truncated at exactly the moment it needs to be persuasive. Front-load the decisive keywords.
- **Prefer pushy over modest.** Models tend to *under*-trigger skills. Name the adjacent situations explicitly instead of trusting the reader to generalize.

Compare:

```yaml
# Fails: no triggers, no boundary, nothing to match against.
description: Helps with deploying things.

# Works: capability, concrete triggers, and the near-miss it should not claim.
description: Deploy this repo's services to the staging and production hosts, including rollback. Use when the user asks to ship, deploy, promote, roll back, or release a service, or mentions staging/production hosts. Not for writing Dockerfiles or CI config.
```

## 3. Draft SKILL.md

Match the level of prescription to how fragile the task is. This is the most consequential structural choice:

| Freedom | Use when | Form |
|---|---|---|
| High | Many valid approaches; context decides | Prose describing the goal and the tradeoffs |
| Medium | A preferred pattern exists, variation is fine | A template or parameterized script |
| Low | Fragile, ordered, or destructive; consistency is critical | An exact command, marked as not-to-be-modified |

Think of the reader as walking a path: a narrow bridge with cliffs on both sides needs guardrails, an open field needs only a direction.

Write the body in the imperative and cut what the model already knows. Every line competes with the conversation for context, so challenge each one: does this change behaviour, or does it just narrate? Explanation of *why* a rule matters usually earns its tokens and generalizes better than an unqualified `MUST`; background about what the domain is usually does not.

Structure the body for a reader who is skimming:

- Numbered workflow steps for anything sequential, with a copyable checklist when there are more than three.
- Concrete input/output examples wherever output style is the point — examples transfer formatting far better than adjectives.
- Decision points written as explicit branches ("Creating new content? Follow the creation workflow. Editing existing? Follow the edit workflow.").
- A verification or feedback step for anything quality-critical, so the agent can catch its own errors before finishing.

Keep it under 500 lines. That is a working limit, not a hard rule — but approaching it means step 4 is overdue.

## 4. Split detail out as the body grows

Move anything that is only sometimes relevant out of `SKILL.md` into the bundle:

```
writing-skills/
├── SKILL.md          # Routing + the always-true workflow
├── references/       # Long-form docs the agent reads on demand
├── scripts/          # Executable code, run without being read
└── assets/           # Templates and static files used in output
```

Three patterns cover most cases:

- **Guide with references** — `SKILL.md` keeps the quick start and links out (`See [references/forms.md](references/forms.md) for the full form-filling guide`).
- **Domain split** — one file per variant (`references/aws.md`, `references/gcp.md`) so a GCP task never loads the AWS page.
- **Conditional depth** — basic path inline, advanced paths linked (`For tracked changes, see references/redlining.md`).

Rules that keep the structure navigable:

- Reference files **one level deep** from `SKILL.md`. Chained references (`SKILL.md` → `a.md` → `b.md`) get partially read, because the agent previews rather than follows. Link every reference directly from `SKILL.md`.
- Give reference files longer than 100 lines a table of contents, so a partial read still reveals the full scope.
- Name files for their content (`form_validation_rules.md`, not `doc2.md`).
- Always use forward slashes in paths, even on Windows; backslashes break on other platforms.
- Say whether a script is meant to be **executed** ("Run `scripts/validate.py` on the skill") or **read as reference** ("See `scripts/validate.py` for the parsing rules"). The agent cannot infer this.

Prefer a bundled script over prose for anything deterministic or repeated. A script costs no context when executed, produces the same answer every time, and stops every future run from reinventing the same code. Write it defensively: handle the missing-file and bad-input cases inside the script instead of returning a stack trace for the agent to interpret, and justify any constant that looks arbitrary.

## 5. Validate, then test on real prompts

Run the bundled validator first. It checks the mechanical contract that hosts enforce silently:

```bash
python scripts/validate_skill.py <path-to-skill-directory>
```

Malformed skills are usually dropped without a visible error — the host logs a warning and the agent simply never sees them, which looks identical to a skill that does not trigger. The validator turns that silence into a diagnosis. See [references/spec.md](references/spec.md) for the full field-by-field contract.

The validator ships with its own fixtures. `python scripts/test_validate_skill.py` builds 15 deliberately broken skills and asserts each one is diagnosed, so a bug in the checker cannot masquerade as a passing skill. Run it after editing the validator, not on every skill.

Then test on real prompts, not invented ones. Write three tasks of the kind the user would genuinely type, including one that is a plausible *near-miss* which should **not** trigger the skill. For each, observe:

- Did the skill load at all? If not, the description is the suspect.
- Did the agent follow the workflow, or wander off it? Wandering usually means the structure is unclear or a step is buried.
- Did it read files in an unexpected order, or ignore a bundled file? Ignored content is either unnecessary or badly signposted.
- Did it invent something the skill should have specified?

Where output is objectively checkable, compare a run with the skill against a run without it. A skill that does not beat the baseline on its own test cases is not earning its context. [references/iteration.md](references/iteration.md) covers the evaluation loop in depth, including the heavyweight option.

## Revising an existing skill

Diagnose before rewriting, because each symptom has a different cause:

| Symptom | Likely cause | Fix |
|---|---|---|
| Never triggers | Description lacks the user's vocabulary, or the task is simple enough to need no skill | Rewrite the description with real trigger phrases |
| Triggers on the wrong task | Description is too broad or claims adjacent work | Add a boundary clause naming what it excludes |
| Loads but is ignored | Body is long, flat, or buried under background | Cut preamble, promote the workflow, push detail to references |
| Agent skips a critical step | Step is not prominent or not ordered | Make it a numbered step, or move it earlier |
| Agent improvises instead of following | Task is fragile but instructions are loose | Lower the freedom level: give the exact command |
| Inconsistent output shape | Format described in prose only | Add a literal template or input/output examples |

When revising, preserve the existing `name` and directory name. Renaming breaks user invocation (`/name`) and any reference to the skill.

## DSH essentials

These are the facts that cause silent failures. The full contract is in [references/spec.md](references/spec.md).

- **Layout.** A skill is `<root>/<name>/SKILL.md` or a flat `<root>/<name>.md`. Nested `**/SKILL.md` files are **not** discovered — depth beyond the root's immediate children is invisible.
- **Roots**, scanned in priority order: `<project>/.dsh/skills`, `<project>/.agents/skills`, configured custom dirs, `~/.dsh/skills`, `~/.agents/skills`. Project root is the nearest ancestor containing `.git`, falling back to the current directory.
- **Required frontmatter:** `name` and `description`. `name` must match `/^[a-z0-9]+(?:-[a-z0-9]+)*$/` and should match its directory name.
- **Optional frontmatter:** `whenToUse` (camelCase), `metadata`, `disable-model-invocation`, `user-invocable` (kebab-case). The camelCase legacy spellings of the invocation keys — `disableModelInvocation`, `modelInvocable`, `userInvocable` — are **rejected** and drop the whole skill.
- **Booleans** accept YAML booleans plus the case-insensitive `true`/`false`, `yes`/`no`, `on`/`off`, `1`/`0`. Any other value drops the skill.
- **Use kebab-case, gerund names** (`writing-skills`, `analyzing-logs`). They read consistently in a catalog and match the ecosystem convention.
- **Live pickup.** Roots are watched; a new or edited skill reaches the next step without a restart. Editing frontmatter refreshes the catalog; editing files under `references/` or `scripts/` does not, but each load re-reads the body.

## References

Read these when the summary above is not enough:

- [references/spec.md](references/spec.md) — the complete skill contract: frontmatter fields, validation rules, discovery roots, packaging, and portability to other hosts.
- [references/authoring.md](references/authoring.md) — the craft in depth: description engineering, progressive disclosure patterns, writing style, and the anti-patterns that waste context.
- [references/iteration.md](references/iteration.md) — evaluation-driven development, grading, and when to reach for the heavyweight tooling.

Before shipping a skill, walk [references/authoring.md](references/authoring.md) § Final checklist.
