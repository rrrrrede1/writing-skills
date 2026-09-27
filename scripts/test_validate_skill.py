#!/usr/bin/env python3
"""Self-test for validate_skill.py.

Each fixture is a deliberately malformed skill paired with what the validator
must report. This matters because the validator's whole job is to catch
failures the host swallows silently: if the validator itself is wrong, it
produces false confidence instead of a diagnosis.

Run:
    python scripts/test_validate_skill.py
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# The validator is imported, not run as a subprocess; keep Python from dropping
# a __pycache__ directory into the skill bundle.
sys.dont_write_bytecode = True


def load_validator():
    spec = importlib.util.spec_from_file_location("validate_skill", HERE / "validate_skill.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


GOOD_BODY = "\n\nA perfectly ordinary instruction body.\n"

#: fixture name -> (relative file path -> contents, expected exit, expected substrings)
FIXTURES: dict[str, tuple[dict[str, str], int, tuple[str, ...]]] = {
    "valid-bundle": (
        {
            "SKILL.md": (
                "---\n"
                "name: valid-bundle\n"
                "description: Do a specific useful thing when the user asks for it.\n"
                "whenToUse: The user asks for the thing.\n"
                "metadata:\n"
                "  version: '1.0'\n"
                "disable-model-invocation: false\n"
                "user-invocable: yes\n"
                "---\n" + GOOD_BODY
            )
        },
        0,
        ("OK:",),
    ),
    "legacy-invocation-key": (
        {
            "SKILL.md": (
                "---\n"
                "name: legacy-invocation-key\n"
                "description: A description that is long enough to be plausible.\n"
                "disableModelInvocation: true\n"
                "---\n" + GOOD_BODY
            )
        },
        1,
        ("disableModelInvocation", "disable-model-invocation"),
    ),
    "bad-name-uppercase": (
        {
            "SKILL.md": (
                "---\n"
                "name: Bad_Name\n"
                "description: A description that is long enough to be plausible.\n"
                "---\n" + GOOD_BODY
            )
        },
        1,
        ("invalid",),
    ),
    "missing-description": (
        {"SKILL.md": "---\nname: missing-description\n---\n" + GOOD_BODY},
        1,
        ("description",),
    ),
    "bad-boolean": (
        {
            "SKILL.md": (
                "---\n"
                "name: bad-boolean\n"
                "description: A description that is long enough to be plausible.\n"
                "user-invocable: maybe\n"
                "---\n" + GOOD_BODY
            )
        },
        1,
        ("not a recognised boolean",),
    ),
    "no-frontmatter": (
        {"SKILL.md": "# Just a document\n\nNo frontmatter here.\n"},
        1,
        ("begin with '---'",),
    ),
    "unclosed-frontmatter": (
        {"SKILL.md": "---\nname: unclosed-frontmatter\ndescription: Something.\n"},
        1,
        ("never closed",),
    ),
    "broken-link": (
        {
            "SKILL.md": (
                "---\n"
                "name: broken-link\n"
                "description: A description that is long enough to be plausible.\n"
                "---\n"
                "See [the guide](references/guide.md) for more.\n"
            )
        },
        1,
        ("does not exist",),
    ),
    "when-to-use-typo": (
        {
            "SKILL.md": (
                "---\n"
                "name: when-to-use-typo\n"
                "description: A description that is long enough to be plausible.\n"
                "when-to-use: Something the parser ignores.\n"
                "---\n" + GOOD_BODY
            )
        },
        0,
        ("unknown frontmatter key", "whenToUse"),
    ),
    "illustrative-links-in-code": (
        {
            "SKILL.md": (
                "---\n"
                "name: illustrative-links-in-code\n"
                "description: A description that is long enough to be plausible.\n"
                "---\n"
                "Links inside code are examples, not references:\n\n"
                "`See [x](references/nope.md)`\n\n"
                "```markdown\nSee [y](references/also-nope.md)\n```\n"
            )
        },
        0,
        ("OK:",),
    ),
    "deeply-nested-skill": (
        {
            "skills/outer/deeply-nested-skill/SKILL.md": (
                "---\n"
                "name: deeply-nested-skill\n"
                "description: A description that is long enough to be plausible.\n"
                "---\n" + GOOD_BODY
            )
        },
        1,
        ("one level deep",),
        "skills/outer/deeply-nested-skill",
    ),
    "long-description": (
        {
            "SKILL.md": (
                "---\n"
                "name: long-description\n"
                "description: " + ("word " * 130) + "\n"
                "---\n" + GOOD_BODY
            )
        },
        0,
        ("truncated",),
    ),
    "backslash-paths": (
        {
            "SKILL.md": (
                "---\n"
                "name: backslash-paths\n"
                "description: A description that is long enough to be plausible.\n"
                "---\n"
                "Run scripts\\runner.py to do the thing.\n"
            )
        },
        0,
        ("forward",),
    ),
    "reference-without-toc": (
        {
            "SKILL.md": (
                "---\n"
                "name: reference-without-toc\n"
                "description: A description that is long enough to be plausible.\n"
                "---\n"
                "See [the guide](references/guide.md).\n"
            ),
            "references/guide.md": "\n".join(f"Line {n}" for n in range(140)),
        },
        0,
        ("Contents",),
    ),
    "lateral-link-is-fine": (
        {
            "SKILL.md": (
                "---\n"
                "name: lateral-link-is-fine\n"
                "description: A description that is long enough to be plausible.\n"
                "---\n"
                "See [a](references/a.md) and [b](references/b.md).\n"
            ),
            "references/a.md": "## Contents\n\nOnward to [b](b.md).\n",
            "references/b.md": "## Contents\n\nNothing onward.\n",
        },
        0,
        ("OK:",),
    ),
}


def default_scratch_root() -> Path:
    """Pick a directory that does not sit under a 'skills' root.

    The validator flags skills nested more than one level below a `skills`
    directory, which is correct behaviour but would make every fixture fail if
    the tests were written inside the skill bundle itself.
    """
    override = os.environ.get("SKILL_VALIDATOR_TMP")
    if override:
        return Path(override)
    candidate = Path.cwd().resolve()
    while "skills" in candidate.parts and candidate.parent != candidate:
        candidate = candidate.parent
    if candidate.name.startswith(".") and candidate.parent != candidate:
        candidate = candidate.parent
    return candidate


def run_fixture(
    validator, root: Path, fixture_name: str, files: dict[str, str], target: str
) -> tuple[int, str]:
    # The directory is named after the skill so the layout check passes.
    skill_dir = root / fixture_name
    for relative, contents in files.items():
        path = skill_dir / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        exit_code = validator.main(["validate_skill.py", str(skill_dir / target)])
    return exit_code, buffer.getvalue()


def main() -> int:
    validator = load_validator()
    failures: list[str] = []

    # Fixtures are written into the current working directory rather than the
    # system temp: sandboxed agent environments often deny writes there. The
    # directory is created explicitly rather than with tempfile.mkdtemp, whose
    # restrictive mode some sandboxes refuse to let a child directory inherit.
    scratch = default_scratch_root() / f"skill-validator-test-{os.getpid()}"
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir()
    try:
        for fixture_name, fixture in FIXTURES.items():
            files, expected_exit, expected_substrings = fixture[:3]
            target = fixture[3] if len(fixture) > 3 else "."
            exit_code, output = run_fixture(validator, scratch, fixture_name, files, target)

            problems: list[str] = []
            if exit_code != expected_exit:
                problems.append(f"exit {exit_code}, expected {expected_exit}")
            for expected in expected_substrings:
                if expected not in output:
                    problems.append(f"missing {expected!r}")

            if problems:
                failures.append(fixture_name)
                print(f"FAIL  {fixture_name}: {'; '.join(problems)}")
                for line in output.strip().splitlines():
                    print(f"        | {line}")
            else:
                print(f"ok    {fixture_name}")
    finally:
        shutil.rmtree(scratch, ignore_errors=True)

    print()
    if failures:
        print(f"{len(failures)} of {len(FIXTURES)} fixtures failed")
        return 1
    print(f"all {len(FIXTURES)} fixtures passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
