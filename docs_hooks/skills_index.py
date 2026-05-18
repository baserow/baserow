"""
mkdocs hook: replace the <!-- SKILLS:AUTO --> marker in
docs/development/skills-index.md with an auto-generated list of skills.

Each skill is read from `.agents/skills/*/SKILL.md`. The YAML frontmatter
provides the `description`; the folder name is the slug. The page only
contains that marker where the listing should appear. The generated
listing lives nowhere on disk, so it cannot drift from the skill metadata.

Wire in mkdocs.yml:

    hooks:
      - docs_hooks/skills_index.py

Trigger a rebuild after adding/renaming/removing a skill, or after
editing a SKILL.md `description`. `mkdocs serve` picks it up
automatically because the .agents/skills/ tree is walked on every build.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / ".agents" / "skills"
GITHUB_BASE = "https://github.com/baserow/baserow/blob/develop/.agents/skills"
MARKER = "<!-- SKILLS:AUTO -->"
TARGET_PAGE = "development/skills-index.md"


def _load_skill(skill_dir: Path) -> dict | None:
    """Return {slug, description} parsed from a SKILL.md, or None if missing.

    The display label is always the folder slug (kebab-case), not the
    frontmatter ``name`` — skill authors are inconsistent about casing
    there, and the slug is what's referenced throughout the rest of the
    docs and the runtime.
    """

    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return None

    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return None

    # Frontmatter is the YAML block between the first two `---` lines.
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return None

    description = meta.get("description") or ""
    return {"slug": skill_dir.name, "description": description}


def _render() -> str:
    """Build the markdown listing of skills."""

    if not SKILLS_DIR.is_dir():
        return f"_(No skills found at `{SKILLS_DIR.relative_to(REPO_ROOT)}`.)_"

    skills = []
    for entry in sorted(SKILLS_DIR.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        loaded = _load_skill(entry)
        if loaded is not None:
            skills.append(loaded)

    if not skills:
        return "_(No skills found.)_"

    lines = []
    for skill in skills:
        url = f"{GITHUB_BASE}/{skill['slug']}/SKILL.md"
        lines.append(f"- **[`{skill['slug']}`]({url})** — {skill['description']}")
    return "\n".join(lines)


def on_page_markdown(markdown, page, config, files):
    """Replace the marker on the target page with the rendered listing."""

    if page.file.src_uri != TARGET_PAGE:
        return markdown

    if MARKER not in markdown:
        return markdown

    return markdown.replace(MARKER, _render())
