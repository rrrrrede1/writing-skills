#!/usr/bin/env python3
"""Validate an agent skill against the discovery contract.

Skills that violate the contract are usually dropped without any visible
error: the host logs a warning and the agent never learns the skill exists,
which looks identical to a skill that simply never triggers. This script
turns that silence into a diagnosis.

Usage:
    python validate_skill.py <skill-directory-or-SKILL.md>

Exit codes:
    0  no errors (warnings may still be present)
    1  at least one error
    2  the path itself could not be read

Standard library only; no dependencies.
"""

from __future__ import annotations

import difflib
import re
import sys
from pathlib import Path

# --- Contract constants -----------------------------------------------------

NAME_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
NAME_MAX_LENGTH = 64
DESCRIPTION_CATALOG_MAX = 500
BODY_LINE_LIMIT = 500
TOC_LINE_THRESHOLD = 100

REQUIRED_FIELDS = ("name", "description")
MAPPED_FIELDS = ("metadata",)
BOOLEAN_FIELDS = ("disable-model-invocation", "user-invocable")
STRING_FIELDS = ("whenToUse", "license", "compatibility", "allowed-tools")

#: Keys the parser rejects outright, mapped to their replacement.
REJECTED_KEYS = {
    "disableModelInvocation": "disable-model-invocation",
    "modelInvocable": "disable-model-invocation",
    "userInvocable": "user-invocable",
}

KNOWN_FIELDS = set(REQUIRED_FIELDS + MAPPED_FIELDS + BOOLEAN_FIELDS + STRING_FIELDS)

TRUE_SPELLINGS = {"true", "yes", "on", "1"}
FALSE_SPELLINGS = {"false", "no", "off", "0"}

LINK_PATTERN = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
FENCE_PATTERN = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
WINDOWS_PATH_PATTERN = re.compile(
    r"[A-Za-z0-9_.\-]+\\[A-Za-z0-9_.\-]+\.(?:md|py|sh|js|ts|json|txt|ya?ml)"
)


INLINE_CODE_PATTERN = re.compile(r"``[^`]*``|`[^`\n]*`")


def strip_literal_code(text: str) -> str:
    """Blank out code before scanning for links.

    Fenced blocks and inline spans hold illustrative examples — template
    paths, sample references — that are not live links. Scanning them produces
    false "broken reference" reports, and a validator that cries wolf gets
    ignored.

    A closing fence must use the same character and be at least as long as the
    opening one, so a ``` block nested in a ```` block does not close it early.
    """
    output: list[str] = []
    fence_char: str | None = None
    fence_length = 0
    for line in text.splitlines():
        match = FENCE_PATTERN.match(line)
        if fence_char is None:
            if match:
                fence_char = match.group(1)[0]
                fence_length = len(match.group(1))
                output.append("")
                continue
            output.append(INLINE_CODE_PATTERN.sub("", line))
        else:
            if (
                match
                and match.group(1)[0] == fence_char
                and len(match.group(1)) >= fence_length
            ):
                fence_char = None
                fence_length = 0
            output.append("")
    return "\n".join(output)


class Report:
    """Collects findings so the whole skill can be checked before failing."""

    def __init__(self) -> None:
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.notes: list[str] = []

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    def note(self, message: str) -> None:
        self.notes.append(message)

    def render(self) -> None:
        for message in self.notes:
            print(f"  note  {message}")
        for message in self.warnings:
            print(f"  WARN  {message}")
        for message in self.errors:
            print(f"  FAIL  {message}")


# --- Minimal frontmatter parsing -------------------------------------------
# Only the subset the skill format uses: top-level scalars and one level of
# nesting for map-valued fields. Avoids a PyYAML dependency on purpose.


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _strip_comment(line: str) -> str:
    """Remove a trailing comment that is not inside quotes."""
    quote: str | None = None
    for index, char in enumerate(line):
        if quote:
            if char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "#" and (index == 0 or line[index - 1] in " \t"):
            return line[:index]
    return line


def parse_frontmatter(text: str, report: Report) -> tuple[dict, str] | None:
    """Return (frontmatter mapping, body) or None when unusable."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        report.error(
            "no YAML frontmatter found. The file must begin with '---' on its "
            "very first line, with no blank line or heading above it."
        )
        return None

    closing = None
    for index in range(1, len(lines)):
        if lines[index].strip() == "---":
            closing = index
            break
    if closing is None:
        report.error(
            "frontmatter starts with '---' but is never closed. Add a closing "
            "'---' line before the Markdown body."
        )
        return None

    data: dict = {}
    seen_keys: set[str] = set()
    nested_target: dict | None = None

    for raw in lines[1:closing]:
        line = _strip_comment(raw)
        if not line.strip():
            continue
        if line[:1] in (" ", "\t"):
            if nested_target is None:
                report.error(
                    f"indented line {line.strip()!r} does not belong to a map-valued "
                    f"field. Nest it under one of: {', '.join(MAPPED_FIELDS)}."
                )
                continue
            key, separator, value = line.strip().partition(":")
            if not separator:
                report.error(f"map entry {line.strip()!r} is missing a ':' separator.")
                continue
            nested_target[_unquote(key)] = _unquote(value)
            continue

        nested_target = None
        key, separator, value = line.partition(":")
        key = key.strip()
        if not separator:
            report.error(f"frontmatter line {raw.strip()!r} is missing a ':' separator.")
            continue
        if key in seen_keys:
            report.warn(f"duplicate frontmatter key {key!r}; the last value wins.")
        seen_keys.add(key)

        if key in REJECTED_KEYS:
            report.error(
                f"frontmatter key {key!r} is rejected by the parser, which drops the "
                f"entire skill. Use the kebab-case spelling {REJECTED_KEYS[key]!r}."
            )
            continue

        if key in MAPPED_FIELDS:
            mapping: dict = {}
            data[key] = mapping
            nested_target = mapping
            if value.strip():
                report.warn(
                    f"{key!r} should be a mapping of indented key/value pairs, "
                    f"not an inline value."
                )
            continue

        data[key] = _unquote(value)

    for key in data:
        if key not in KNOWN_FIELDS:
            suggestion = difflib.get_close_matches(key, KNOWN_FIELDS, n=1)
            hint = f" Did you mean {suggestion[0]!r}?" if suggestion else ""
            report.warn(
                f"unknown frontmatter key {key!r} is silently ignored by the host.{hint}"
            )

    return data, "\n".join(lines[closing + 1 :]).strip()


def validate_frontmatter(data: dict, report: Report) -> str | None:
    """Check field values; return the declared name when it is usable."""
    for field in REQUIRED_FIELDS:
        if field not in data or not str(data[field]).strip():
            report.error(f"required frontmatter field {field!r} is missing or empty.")
    if any(field not in data for field in REQUIRED_FIELDS):
        return None

    name = str(data["name"])
    if not NAME_PATTERN.match(name):
        report.error(
            f"name {name!r} is invalid. It must match {NAME_PATTERN.pattern} — "
            f"lowercase letters, digits, and single hyphens only (no uppercase, "
            f"underscores, or doubled hyphens)."
        )
    if len(name) > NAME_MAX_LENGTH:
        report.error(f"name is {len(name)} characters; the maximum is {NAME_MAX_LENGTH}.")

    description = str(data["description"])
    if len(description) > DESCRIPTION_CATALOG_MAX:
        report.warn(
            f"description is {len(description)} characters and will be truncated at "
            f"{DESCRIPTION_CATALOG_MAX} in the session catalog, hiding its tail during "
            f"skill selection. Front-load the decisive keywords, or shorten it."
        )
    if len(description) < 40:
        report.warn(
            f"description is only {len(description)} characters; it is the entire "
            f"triggering mechanism, so state the capability and the situations that "
            f"should invoke the skill."
        )
    lowered = description.lower()
    if lowered.startswith(("this skill", "guide for", "a skill for")):
        report.warn(
            "description opens with documentary framing rather than an instruction to "
            "the agent; open with the capability instead."
        )

    for field in BOOLEAN_FIELDS:
        if field not in data:
            continue
        value = str(data[field]).strip().lower()
        if value not in TRUE_SPELLINGS | FALSE_SPELLINGS:
            report.error(
                f"{field!r} has value {data[field]!r}, which is not a recognised "
                f"boolean. A rejected spelling drops the whole skill. Use true/false."
            )

    for field in STRING_FIELDS:
        if field in data and not isinstance(data[field], str):
            report.warn(f"{field!r} should be a string.")

    return name


# --- Body, layout, and link checks -----------------------------------------


def validate_layout(skill_dir: Path, name: str, report: Report) -> None:
    """Check the skill is at a depth the host actually scans."""
    directory_name = skill_dir.resolve().name
    if directory_name != name:
        report.warn(
            f"directory name {directory_name!r} does not match the frontmatter name "
            f"{name!r}; they should agree so the catalog and the path stay consistent."
        )

    parts = skill_dir.resolve().parts
    for index in range(len(parts) - 1, -1, -1):
        if parts[index] == "skills":
            # Expected shape below a scan root: skills/<name>
            depth = len(parts) - index - 1
            if depth > 1:
                report.error(
                    "discovery is one level deep, so this skill will not be found at "
                    f"{'/'.join(parts[index:])}. Move it to skills/{name}/."
                )
            break


def validate_body(body: str, report: Report) -> None:
    if not body.strip():
        report.error("the Markdown body is empty; it must carry the instructions.")

    line_count = len(body.splitlines())
    if line_count > BODY_LINE_LIMIT:
        report.warn(
            f"body is {line_count} lines, over the {BODY_LINE_LIMIT}-line guideline. "
            f"Move detail that is only sometimes relevant into references/ and link it "
            f"from SKILL.md."
        )

    matches = WINDOWS_PATH_PATTERN.findall(body)
    if matches:
        report.warn(
            f"backslash paths found ({', '.join(sorted(set(matches))[:3])}); use forward "
            f"slashes so the skill works on non-Windows hosts."
        )


def extract_local_targets(text: str) -> list[str]:
    """Return de-duplicated relative link targets, in order of appearance."""
    targets: list[str] = []
    for target in LINK_PATTERN.findall(strip_literal_code(text)):
        cleaned = target.split("#", 1)[0].strip()
        if not cleaned or cleaned.lower().startswith(("http://", "https://", "mailto:", "#")):
            continue
        if cleaned not in targets:
            targets.append(cleaned)
    return targets


def validate_links(body: str, skill_dir: Path, report: Report) -> None:
    """Check references resolve, stay one level deep, and are navigable."""
    local_targets = extract_local_targets(body)
    if not local_targets:
        return

    report.note(f"{len(local_targets)} linked resource(s) referenced from SKILL.md")

    # Anything SKILL.md links to directly is one level deep, by definition.
    direct = {(skill_dir / target).resolve() for target in local_targets}

    for target in local_targets:
        resolved = (skill_dir / target).resolve()
        if not resolved.exists():
            report.error(
                f"linked file {target!r} does not exist. A broken reference sends the "
                f"agent looking for a file that is not there."
            )
            continue
        if resolved.suffix == ".md":
            _validate_reference_file(resolved, target, direct, report)


def _validate_reference_file(
    path: Path, label: str, direct: set[Path], report: Report
) -> None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        report.warn(f"could not read {label!r} to check its contents: {error}")
        return

    lines = text.splitlines()
    if len(lines) > TOC_LINE_THRESHOLD and not re.search(
        r"^#{1,3}\s+Contents\b", text, re.MULTILINE | re.IGNORECASE
    ):
        report.warn(
            f"{label!r} is {len(lines)} lines with no '## Contents' section; a table of "
            f"contents lets a partial read reveal the file's full scope."
        )

    # A link onward is only a problem when it creates a second hop: a file that
    # SKILL.md does not link directly, and so is reachable only through this one.
    nested = [
        target
        for target in extract_local_targets(text)
        if (path.parent / target).resolve() not in direct
    ]
    if nested:
        report.warn(
            f"{label!r} links onward to {', '.join(sorted(set(nested))[:3])}, which "
            f"SKILL.md does not link directly. Keep references one level deep; chained "
            f"references get partially read."
        )


# --- Entry point ------------------------------------------------------------


def resolve_target(argument: str) -> tuple[Path, Path] | None:
    """Return (skill_directory, skill_file) for a directory or file argument."""
    path = Path(argument)
    if path.is_dir():
        candidate = path / "SKILL.md"
        if not candidate.is_file():
            flat = sorted(path.glob("*.md"))
            if len(flat) == 1:
                return path, flat[0]
            return None
        return path, candidate
    if path.is_file():
        return path.parent, path
    return None


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__.strip())
        return 2

    resolved = resolve_target(argv[1])
    if resolved is None:
        print(f"error: no SKILL.md or unique flat .md file found at {argv[1]!r}")
        return 2

    skill_dir, skill_file = resolved
    print(f"Validating {skill_file}")
    try:
        text = skill_file.read_text(encoding="utf-8")
    except OSError as error:
        print(f"error: could not read {skill_file}: {error}")
        return 2

    report = Report()
    parsed = parse_frontmatter(text, report)
    if parsed is not None:
        data, body = parsed
        name = validate_frontmatter(data, report)
        if name:
            validate_layout(skill_dir, name, report)
            validate_links(body, skill_dir, report)
        validate_body(body, report)

    report.render()

    print()
    if report.errors:
        print(f"FAILED: {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
        return 1
    print(f"OK: no errors, {len(report.warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
