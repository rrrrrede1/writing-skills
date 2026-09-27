# Iterating on a Skill

## Contents

- [Why evaluate](#why-evaluate)
- [Evaluation-driven development](#evaluation-driven-development)
- [Running the comparison](#running-the-comparison)
- [Grading](#grading)
- [Optimizing the description](#optimizing-the-description)
- [Reading the results](#reading-the-results)
- [When to reach for heavier tooling](#when-to-reach-for-heavier-tooling)

## Why evaluate

A skill is a hypothesis: that the agent, given this context, does the job better than it would alone. That hypothesis is cheap to test and expensive to assume. The failure mode of an untested skill is quiet — it appears to work on the author's mental example, then underperforms on the real distribution of tasks while consuming context on every single session.

Two properties make evaluation worth the effort:

- **Skills are used many times.** A flaw is not a one-off cost; it compounds across every future invocation.
- **The author is the worst judge of clarity.** You know what you meant. A fresh agent with only the skill loaded does not.

## Evaluation-driven development

The order matters. Write the evaluation before writing the documentation, so the skill addresses observed gaps instead of imagined ones.

1. **Identify the gap.** Run the agent on representative tasks *without* the skill. Record the specific failures: what it missed, what it invented, what it had to be told twice.
2. **Write three scenarios.** Turn those failures into tasks. Include a near-miss that should *not* trigger the skill.
3. **Establish the baseline.** Capture what the agent does unaided. This is the number the skill has to beat.
4. **Write the minimum.** Add just enough instruction to close the observed gap. Not the theoretical complete guide — the delta.
5. **Re-run and compare.** Improve where the skill loses, and delete anything that never changes the outcome.

Step 5 is where skills get good. The instinct is to add; the leverage is usually in removing.

## Running the comparison

For each test case, run the task twice: once with the skill loaded, once without. Keep the prompts byte-identical — the only variable should be the skill.

If the skill is registered as a *file* in a shared workspace, the two arms need
different filesystem states and cannot run at the same time. Run them
sequentially and reset state between runs, or the first arm's artifacts leak into
the second:

1. Move the skill bundle **outside the workspace** for the baseline arm. Taking
   it out of the catalog is not enough — an agent that explores the filesystem
   will still find it. This also means removing any note, spec, or README in the
   workspace that describes the expected answer.
2. Snapshot and restore any fixture the task mutates.
3. Delete the artifacts each run produces before starting the next one, or the
   earlier run's skill becomes a distractor in the next run's catalog.

When the skill is provided by an external service rather than the filesystem, or
when you are comparing two self-contained prompt variants, running the arms
concurrently is fine and faster.

Give a delegated run a complete brief: the task prompt, the input files, where to write outputs, and which artifacts matter.

```
Execute this task:
- Skill: <path-to-skill>        (omit for the baseline run)
- Task: <the eval prompt>
- Input files: <paths, or "none">
- Save outputs to: <workspace>/iteration-<N>/<eval-name>/with_skill/
- Outputs to capture: <the artifacts the user cares about>
```

Two baselines are meaningful, depending on the work:

- **New skill** — no skill at all. The question is whether the skill adds anything.
- **Revised skill** — the previous version. Snapshot the old skill *before* editing, then point the baseline run at the snapshot. The question is whether the revision is actually better.

Organize runs by iteration so a regression is visible:

```
my-skill-workspace/
├── iteration-1/
│   ├── extract-tables/
│   │   ├── with_skill/
│   │   └── without_skill/
│   └── near-miss-should-not-trigger/
└── iteration-2/
```

Note for each run whether the skill actually loaded. A with-skill run where the skill never triggered is a description bug, not a body bug, and needs a different fix.

## Grading

Where the output is objectively checkable, define assertions that a script can verify. Good assertions are specific enough to read at a glance in a results table:

```json
{
  "eval_name": "extract-tables",
  "prompt": "Pull the pricing table out of this PDF and give me a CSV.",
  "assertions": [
    "Writes a file named pricing.csv",
    "CSV has a header row with the columns from the source table",
    "Every row from the source table appears exactly once",
    "Numeric values are not quoted"
  ]
}
```

Prefer a script over eyeballing for anything programmatic: it is faster, more reliable, and reusable across iterations. Reserve human judgment for output that is genuinely subjective — writing style, design quality, tone. Forcing assertions onto taste-based work produces noise that looks like signal.

Record pass/fail with the evidence, so a later reader can see *why* an assertion passed rather than trusting the score:

```json
{
  "assertion": "Every row from the source table appears exactly once",
  "passed": true,
  "evidence": "Source has 24 data rows; pricing.csv has 24 data rows with matching IDs."
}
```

## Optimizing the description

When a skill is right but does not trigger reliably, the description is the lever. Optimize it against a labelled query set rather than intuition.

Build 20 realistic queries: 8–10 that should trigger and 8–10 that should not.

- **Make them realistic.** Real prompts carry file paths, typos, abbreviations, casual framing, and backstory. `"Format this data"` tests nothing; `"ok so my boss sent me this xlsx (in downloads, something like 'Q4 sales final FINAL v2.xlsx') and wants a profit margin % column, revenue is col C and cost is col D i think"` tests retrieval.
- **Make the negatives hard.** A PDF skill's negative case should not be "write a fibonacci function". It should be a query that shares vocabulary with the skill but needs something else — the near-miss is the only negative that carries information.
- **Cover phrasings, not just topics.** Formal and casual versions of the same intent, with and without the domain noun.

Then measure: run each query several times against the candidate description and record the trigger rate. Split train and held-out sets, propose changes from the train failures, and select the winner on the held-out score — otherwise you overfit the description to the queries you wrote.

Note how triggering actually works when designing queries: the agent consults a skill when the description matches *and* it cannot trivially handle the task alone. A trivial request like "read this file" will not trigger a skill no matter how good the description is. Test queries must be substantial enough that consulting a skill would genuinely help.

## Reading the results

Look past the headline pass rate, which hides the most useful signals:

- **Assertions that always pass** in both arms are non-discriminating and should be dropped — they add confidence without adding information.
- **High-variance cases** are flaky, or the skill is ambiguous. Read the transcripts before blaming the model.
- **Token and time cost.** A skill that improves quality 5% at triple the tokens is usually a bad trade. Track both arms.
- **Repeated work across runs.** If every run independently writes the same helper script, that script belongs in `scripts/`. This is the highest-value signal the transcripts offer.
- **Unused resources.** A bundled file no run ever opens is either unnecessary or badly signposted.
- **Unexpected trajectories.** Reading files in a strange order usually means the intended path is not obvious from the body.

## When to reach for heavier tooling

This reference covers the loop you can run with the tools in this session: subagents for parallel with/without runs, scripts for assertions, and a human reading the outputs. That is sufficient for most skills.

Anthropic maintains a much heavier `skill-creator` skill with an automated benchmark aggregator, a browser-based review viewer, blind A/B comparison, and an automated description-optimization loop. It is worth knowing about and worth borrowing ideas from, but it is not a drop-in here:

- Its `SKILL.md` alone is roughly 33 KB (well past the 500-line guidance it teaches), plus ~230 KB of bundled scripts, agents, and HTML.
- It assumes `claude` CLI availability, `nohup`/`kill`, `/tmp/` paths, and a browser or display — none of which hold on Windows or in every harness.
- Its frontmatter predates the DSH extension fields and its bundled scripts validate against the portable spec, not this host's discovery rules.

Reach for it deliberately, if at all: fetch `anthropics/skills` → `skills/skill-creator/`, read it against [spec.md](spec.md), and port only the parts that earn their cost. For validating structure, the bundled `scripts/validate_skill.py` here is already the right tool — it targets this host's actual parser.
