"""Utilities for diagram authoring support in the editor and tests."""

from __future__ import annotations

import re
from typing import Dict, List

LANGUAGE_ALIASES = {
    "mermaid": "mermaid",
    "flowchart": "mermaid",
    "sequence": "mermaid",
    "mindmap": "mermaid",
    "erd": "mermaid",
    "network": "mermaid",
    "database": "mermaid",
    "datastructure": "mermaid",
    "dot": "graphviz",
    "graphviz": "graphviz",
    "digraph": "graphviz",
    "uml": "nomnoml",
    "classdiagram": "nomnoml",
    "nomnoml": "nomnoml",
}

SUBJECT_ENGINE_MAP = {
    "network": ["mermaid", "graphviz"],
    "data_structure": ["mermaid", "nomnoml"],
    "uml": ["nomnoml", "mermaid"],
    "dbms": ["mermaid"],
    "database": ["mermaid"],
    "algorithm": ["mermaid"],
}

FENCED_BLOCK_RE = re.compile(r"```([a-zA-Z0-9_\-]*)\n([\s\S]*?)```")


def extract_fenced_blocks(text: str) -> List[Dict[str, str]]:
    """Extract fenced code blocks with language and line number metadata."""
    src = str(text or "")
    blocks: List[Dict[str, str]] = []

    for match in FENCED_BLOCK_RE.finditer(src):
        lang = (match.group(1) or "").strip().lower()
        code = (match.group(2) or "").strip()
        start_pos = match.start()
        line_number = src.count("\n", 0, start_pos) + 1
        blocks.append({
            "lang": lang,
            "code": code,
            "line": line_number,
        })

    return blocks


def resolve_engine(lang: str, code: str = "", subject_id: str = "") -> str:
    """Resolve diagram engine from language, code shape, and optional subject fallback."""
    lang_key = str(lang or "").strip().lower()
    if lang_key in LANGUAGE_ALIASES:
        return LANGUAGE_ALIASES[lang_key]

    code_text = str(code or "")
    if re.search(r"^\s*(graph\s+\w+|digraph\s+\w+)", code_text, flags=re.IGNORECASE):
        return "graphviz"
    if re.search(r"\b(flowchart|sequenceDiagram|classDiagram|erDiagram|stateDiagram|mindmap)\b", code_text, flags=re.IGNORECASE):
        return "mermaid"
    if re.search(r"^\s*#?title\s*:", code_text, flags=re.IGNORECASE) or re.search(r"\[[^\]]+\]\s*[-:o+<>*]+\s*\[[^\]]+\]", code_text):
        return "nomnoml"

    if lang_key in {"diagram", "chart"}:
        sid = str(subject_id or "").strip().lower()
        preferred = SUBJECT_ENGINE_MAP.get(sid) or []
        return preferred[0] if preferred else ""

    return ""


def validate_diagram_blocks(text: str, subject_id: str = "") -> List[Dict[str, str]]:
    """Return warnings for malformed or unsupported diagram fences."""
    warnings: List[Dict[str, str]] = []

    for block in extract_fenced_blocks(text):
        lang = block["lang"]
        code = block["code"]
        line = block["line"]

        if lang in {"", "plain", "text", "plaintext"}:
            continue

        engine = resolve_engine(lang, code, subject_id)
        if not engine:
            warnings.append({
                "line": str(line),
                "lang": lang,
                "message": f"Unknown diagram language '{lang}'."
            })
            continue

        if not code.strip():
            warnings.append({
                "line": str(line),
                "lang": lang,
                "message": "Diagram block is empty."
            })

    return warnings
