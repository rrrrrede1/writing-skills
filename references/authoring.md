# Authoring Craft

## Contents

- [Conciseness as a budget](#conciseness-as-a-budget)
- [Degrees of freedom](#degrees-of-freedom)
- [Description engineering](#description-engineering)
- [Progressive disclosure patterns](#progressive-disclosure-patterns)
- [Writing style](#writing-style)
- [Working with scripts](#working-with-scripts)
- [Anti-patterns](#anti-patterns)
- [Final checklist](#final-checklist)

## Conciseness as a budget

Once a skill loads, every token in it competes with the conversation history, the system prompt, and the user's actual request. Unlike the metadata, the body is not free.

The operative assumption is that the model is already capable. A skill should add the knowledge the model *does not have*, not re-teach it things it does. Challenge each paragraph:

- Does the model really need this explanation?
- Can I assume it already knows this?
- Does this line change behaviour, or does it just narrate?

A concrete before and after, at roughly a 3× token difference for identical effect:

````markdown
<!-- Verbose: explains the domain instead of stating the instruction -->
PDF (Portable Document Format) files are a common file format that contains
text, images, and other content. To extract text from a PDF, you'll need to
use a library. There are many libraries available for PDF processing, but
pdfplumber is recommended because it's easy to use and handles most cases
well. First, you'll need to install it using pip. Then you can use the code
below...

<!-- Concise: assumes the model knows what a PDF is -->
Use pdfplumber for text extraction:

```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    text = pdf.pages[0].extract_text()
```
````

The bytes saved are not the point. A shorter body is one the agent actually follows, because the instruction is no longer buried in background.

## Degrees of freedom

Match prescription to fragility. The usual failure is over-specifying a judgment task or under-specifying a fragile one.

**High freedom** — prose goals, when multiple approaches are valid and context decides:

```markdown
## Code review process
1. Analyze the structure and organization.
2. Check for potential bugs and edge cases.
3. Suggest improvements for readability and maintainability.
4. Verify adherence to project conventions.
```

**Medium freedom** — a template or parameterized script, when a preferred pattern exists but variation is acceptable:

```markdown
## Generate report
Use this template and customize as needed:

def generate_report(data, format="markdown", include_charts=True):
    # Process data
    # Generate output in the specified format
    # Optionally include visualizations
```

**Low freedom** — one exact command, when the operation is fragile, ordered, or destructive:

```markdown
## Database migration
Run exactly this script:

python scripts/migrate.py --verify --backup

Do not modify the command or add additional flags.
```

The test: how many wrong ways are there? If a wrong way is merely suboptimal, describe the goal. If a wrong way corrupts data, give the exact command.

## Description engineering

The description is a retrieval key, not a summary. It is matched against the user's words, so it must contain the words a user would use — including the ones that are not the skill's own terminology.

Practical moves:

- **Open with a verb.** "Extract text and tables from PDFs" beats "A skill for PDF extraction."
- **List concrete triggers.** File extensions, tool names, domain nouns, the casual phrasing ("the boss sent me a spreadsheet").
- **Name the boundary.** Adjacent tasks the skill should not claim, which is what prevents wrong-task triggering.
- **Add a nudge where the model is likely to hesitate.** Models under-trigger; make the situations explicit rather than assuming generalization.

Do not use first person or documentary framing ("This skill should be used when..."). It reads as metadata about the skill instead of an instruction to the agent.

Worked example:

```yaml
# Weak: passive, no triggers, no boundary.
description: Guide for creating effective skills. This skill should be
  be used when users want to create a new skill.

# Strong: capability, triggers, boundary.
description: Author or revise an agent skill (SKILL.md). Covers choosing a
  trigger description, structuring the body, splitting detail into
  references/ and scripts/, and validating against the skill contract. Use
  when the user wants to create a skill, turn a repeated workflow into a
  skill, fix a skill that never triggers or is silently ignored,
  restructure an oversized SKILL.md, or debug skill frontmatter.
```

When a skill measurably fails to trigger, generate candidate descriptions against a labelled query set rather than guessing — see [iteration.md](iteration.md).

## Progressive disclosure patterns

Three levels, loaded in sequence: metadata (~100 tokens, always present), `SKILL.md` body (on activation, under 500 lines), bundled resources (only when opened, effectively unbounded).

**Pattern 1 — high-level guide with references.** The body carries the common path and links out.

```markdown
## Quick start
Extract text with pdfplumber: ...

## Advanced features
**Form filling**: See [references/forms.md](references/forms.md)
**API reference**: See [references/api.md](references/api.md)
```

**Pattern 2 — domain split.** One file per variant, so an irrelevant domain never loads.

```
bigquery-skill/
├── SKILL.md
└── references/
    ├── finance.md
    ├── sales.md
    └── marketing.md
```

The body becomes a router: "Finance: revenue and billing metrics → `references/finance.md`."

**Pattern 3 — conditional depth.** Basic inline, advanced linked, so complexity is opt-in.

```markdown
## Editing documents
For simple edits, modify the XML directly.
**For tracked changes**: See [references/redlining.md](references/redlining.md)
**For OOXML details**: See [references/ooxml.md](references/ooxml.md)
```

Keep every reference one level deep. When the agent encounters a reference from inside a referenced file, it tends to preview with a partial read rather than following fully, and arrives with incomplete information. Link everything from `SKILL.md`.

## Writing style

- **Imperative mood.** "Extract the fields" rather than "the fields should be extracted."
- **Explain the why.** A stated reason generalizes to cases you did not anticipate; an unexplained `ALWAYS`/`NEVER` does not. If the body is filling with all-caps rules, that is a signal the reasoning is missing.
- **One term per concept.** Do not rotate between "endpoint", "URL", "route", and "path" for the same thing — the agent may read the variation as meaningful.
- **Concrete over abstract.** An input/output pair teaches formatting better than any adjective.
- **No time-sensitive content.** "After August 2025, use the v2 endpoint" rots. State the current method and, if history matters, collect deprecated approaches in an "old patterns" section.
- **Justify constants.** If a timeout is 30 seconds, say why. An unexplained `TIMEOUT = 47` leaves the agent unable to reason about when to change it.
- **Forward slashes only.** `references/guide.md`, never `references\guide.md` — backslashes break on other platforms.
- **Surprise nothing.** A skill's behaviour should match its description. Do not write skills that mislead, exfiltrate data, or facilitate unauthorized access, and do not accept a request to.

## Working with scripts

A bundled script beats prose for anything deterministic: it is more reliable than generated code, costs no context when executed, is faster, and produces consistent results.

The critical distinction is intent. State which one applies:

- **Execute** — "Run `scripts/analyze_form.py input.pdf` to extract the fields." This is the common case.
- **Read as reference** — "See `scripts/analyze_form.py` for the extraction algorithm." Use only for genuinely intricate logic.

Write scripts that solve their own problems instead of handing failures back to the agent:

```python
def process_file(path):
    """Process a file, creating it if it doesn't exist."""
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        # Create the file rather than failing; the caller wants contents.
        print(f"File {path} not found, creating default")
        with open(path, "w") as f:
            f.write("")
        return ""
    except PermissionError:
        # Degrade instead of aborting the task.
        print(f"Cannot access {path}, using default")
        return ""
```

List any external dependency in the skill and confirm it exists in the target environment. Do not assume a package is installed.

For high-stakes or batch work, add a plan-validate-execute step: have the agent write an intermediate plan file, validate it with a script, and only then apply the changes. This catches errors while they are still cheap, keeps the original untouched until the plan is sound, and gives the agent a specific error to act on. Make the validation messages verbose and specific — "Field `signature_date` not found. Available fields: `customer_name`, `order_total`, `signature_date_signed`" tells the agent exactly how to recover.

## Anti-patterns

| Anti-pattern | Why it hurts | Instead |
|---|---|---|
| Restating the domain to the model | Wastes the context the skill just consumed | Assume competence; state only the delta |
| Documentary tone about the skill | Reads as metadata, not instruction | Write imperatively to the agent |
| Documenting imagined problems | Produces unused instructions that still cost tokens | Build from a real failure you observed |
| A menu of options | Splits the agent's judgement and dilutes the default | Give one default, plus an escape hatch |
| Nested reference chains | Causes partial reads and incomplete information | One level deep from `SKILL.md` |
| Vague names (`helper`, `utils`, `documents`) | Unreferenceable and unsearchable | Name the capability |
| Windows paths | Break on Unix hosts | Forward slashes |
| Unexplained magic numbers | The agent cannot judge when to change them | Comment the reasoning |
| `MUST`/`ALWAYS`/`NEVER` in bulk | Rules without reasons do not generalize | Explain the why, then be direct |

## Final checklist

**Structure**
- [ ] Directory is `<name>/SKILL.md` at the top level of a scanned root, not nested deeper
- [ ] `name` matches the directory, is kebab-case, and follows the gerund convention
- [ ] `description` is specific, under 500 characters, front-loads keywords, and states both what and when
- [ ] `SKILL.md` body is under 500 lines
- [ ] Detail that is only sometimes relevant lives in `references/`
- [ ] Every reference is linked directly from `SKILL.md`, one level deep
- [ ] Reference files over 100 lines have a table of contents
- [ ] No time-sensitive statements
- [ ] Terminology is consistent throughout
- [ ] Examples are concrete, not abstract
- [ ] Forward slashes in every path

**Scripts**
- [ ] Each script is marked as "run" or "read as reference"
- [ ] Errors are handled inside the script, not deferred to the agent
- [ ] Every constant is justified
- [ ] Required packages are listed and confirmed available
- [ ] Critical operations have a verification step

**Testing**
- [ ] `python scripts/validate_skill.py <dir>` passes
- [ ] The skill appears in the session catalog
- [ ] Three realistic prompts were tried, including a near-miss that should not trigger
- [ ] With-skill output was compared against a baseline where the output is checkable
- [ ] The user confirmed the result before it was shared
