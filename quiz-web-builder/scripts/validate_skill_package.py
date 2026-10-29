#!/usr/bin/env python3
"""Check that a publishable skill contains only generic instructions and an empty template."""
from pathlib import Path
import re
import sys

ALLOWED = {
    "SKILL.md",
    "assets/quiz-template.html",
    "references/docx-structure-parsing.md",
    "scripts/probe_docx.py",
    "scripts/validate_skill_package.py",
}

def validate(root):
    root = Path(root)
    actual = {p.relative_to(root).as_posix() for p in root.rglob("*")
              if p.is_file() and "__pycache__" not in p.parts}
    problems = []
    if actual - ALLOWED:
        problems.append("Unexpected files: " + ", ".join(sorted(actual - ALLOWED)))
    if ALLOWED - actual:
        problems.append("Missing files: " + ", ".join(sorted(ALLOWED - actual)))
    template = root / "assets/quiz-template.html"
    if template.exists():
        html = template.read_text(encoding="utf-8-sig")
        if html.count("__PAYLOAD__") != 1 or not re.search(r"const DATA\s*=\s*__PAYLOAD__;", html):
            problems.append("Template must contain one empty DATA placeholder, not a question bank.")
        if "data:image/" in html:
            problems.append("Embedded image data is not allowed in the generic template.")
    return problems

if __name__ == "__main__":
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    errors = validate(root)
    if errors:
        print("FAILED\n" + "\n".join(errors))
        raise SystemExit(1)
    print("PASS: generic skill files only; template DATA remains empty. Manual review is still required.")

