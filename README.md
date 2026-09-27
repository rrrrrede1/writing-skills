# writing-skills

A skill that teaches an agent **how to write skills** — and catches the mistakes
your host reports *silently*.

Built for [DSH](https://github.com/deepseek-ai) (DeepSeek Harness), whose skill
parser is stricter than the public spec and drops invalid skills with nothing but
a host-side log line. The craft guidance is portable to any host that supports
`SKILL.md` bundles.

---

## The problem

A skill that is malformed does not error. It disappears.

The host logs a warning, the model is told nothing, and the skill simply never
appears in the catalog — which is **indistinguishable from a skill that never
triggered**. You end up debugging the description when the real fault was a
misspelled frontmatter key.

Two examples that fail this way in DSH:

- `disableModelInvocation` (camelCase) — **rejected**, drops the entire skill. The
  accepted spelling is `disable-model-invocation`.
- `when-to-use` — silently ignored. The field is `whenToUse`.

This skill hands the agent the real contract, plus a validator that turns the
silence into a diagnosis.

## What's inside

```
writing-skills/
├── SKILL.md                        # The authoring loop, revision diagnostics, DSH essentials
├── references/
│   ├── spec.md                     # Full contract: frontmatter, validation, roots, silent failures
│   ├── authoring.md                # Craft: conciseness budget, description engineering, anti-patterns
│   └── iteration.md                # Evaluation-driven development, grading, description tuning
├── scripts/
│   ├── validate_skill.py           # Deterministic contract checker (stdlib only)
│   └── test_validate_skill.py      # 15 fixtures proving the validator catches each failure
├── README.md
└── LICENSE
```

`SKILL.md` is 175 lines — comfortably under the 500-line guideline it teaches.
Detail lives in `references/` and is loaded only when needed.

## Install

A skill is installed by placing its directory in a scanned root. No build step,
no manifest.

| Scope | Path |
|---|---|
| This project only | `<project>/.dsh/skills/writing-skills/` |
| Every project on this machine | `~/.dsh/skills/writing-skills/` |
| Shared with other agent tooling | `~/.agents/skills/writing-skills/` |

```bash
git clone git@github.com:rrrrrede1/writing-skills.git ~/.dsh/skills/writing-skills
```

Roots are watched, so the skill reaches the next agent step without a restart.

## Use

Ask for it in plain language:

> "帮我把这个流程做成一个 skill"
> "turn this workflow into a skill"
> "this skill never triggers, fix it"

Or invoke it explicitly: `/writing-skills`.

It runs a five-step loop — pin the job → write the description first → draft the
body → split detail into `references/` → validate and test on real prompts — and
includes a symptom→cause table for repairing a skill that already exists.

## Validate

```bash
python scripts/validate_skill.py <path-to-skill-directory>
```

Checks the frontmatter contract, name pattern, description length against the
catalog cap, boolean grammar, rejected legacy keys, bundle depth, body length,
reference existence, and one-level reference depth.

```
$ python scripts/validate_skill.py .
Validating ./SKILL.md
  note  3 linked resource(s) referenced from SKILL.md

OK: no errors, 0 warning(s)
```

The validator ships with its own fixtures, because a broken checker is worse than
no checker:

```bash
python scripts/test_validate_skill.py     # all 15 fixtures passed
```

Stdlib only — no `pip install` needed. Requires Python 3.9+.

## The DSH contract, in one table

The rules that actually decide whether a skill loads. Full detail in
[`references/spec.md`](references/spec.md).

| Rule | Value |
|---|---|
| Required fields | `name`, `description` |
| Name pattern | `/^[a-z0-9]+(?:-[a-z0-9]+)*$/` — lowercase, digits, single hyphens |
| Optional fields | `whenToUse` (camelCase), `metadata`, `disable-model-invocation`, `user-invocable` (kebab-case) |
| Rejected keys | `disableModelInvocation`, `modelInvocable`, `userInvocable` — these drop the whole skill |
| Booleans | `true`/`false`, `yes`/`no`, `on`/`off`, `1`/`0` (case-insensitive) |
| Layout | `<root>/<name>/SKILL.md` or `<root>/<name>.md` — **one level deep only** |
| Discovery roots | `<project>/.dsh/skills` → `<project>/.agents/skills` → custom → `~/.dsh/skills` → `~/.agents/skills` |
| Project root | nearest ancestor containing `.git`, else the current directory |
| Catalog description cap | 500 characters — longer descriptions are truncated during selection |

That last row matters more than it looks: an over-long description is cut off at
exactly the moment the model uses it to decide whether to load the skill.

## Was it tested?

Yes, and the answer is honestly mixed. Three prompts, each run against a no-skill
baseline and a with-skill arm, with state reset between every run.

| Prompt | Baseline | With skill |
|---|---|---|
| "turn our manual release checks into a reusable tool" | description **523 chars — over the cap** — opening `This skill should be used when…` | description 459 chars, with an explicit boundary clause |
| "this skill never seems to work, fix it" | diagnosed all faults by reading the provider source itself | diagnosed all faults using the bundled validator |
| near-miss: harden a JSON-output **system prompt** | no skill created | correctly judged irrelevant, did not load, no skill created |

- **No over-triggering** — the failure mode that actually costs tokens is clean.
- **Measurable gain in description quality** — the clearest win, and exactly what
  step 2 of the skill is built around.
- **Smaller gain in diagnosis than expected** — a capable agent can
  reverse-engineer the contract by reading the provider source. The skill's value
  there is speed and the validator, not unique knowledge.

Two methodology failures are documented rather than hidden: the first evaluation
attempt was invalid because hiding the skill from the catalog did not hide it from
the filesystem, and because the author's own research notes leaked the expected
answer. Both runs were discarded and redone. Reproducing them is left as an
exercise in reading `references/iteration.md`.

## Credits

The craft guidance synthesizes, and adapts for DSH:

- [Skill authoring best practices](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices) — Anthropic
- [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) — Anthropic Engineering
- [Agent Skills specification](https://agentskills.io/specification.md) — the open standard

The DSH contract sections were derived by reading this host's implementation
(`@deepseek-ai/dsh-skill`, `dsh-skill-filesystem`) rather than its documentation,
because the two disagree. No code was copied from
[anthropics/skills](https://github.com/anthropics/skills); its heavier
`skill-creator` is discussed and deliberately not bundled — see
`references/iteration.md`.

## License

MIT — see [LICENSE](LICENSE).
