#!/usr/bin/env python3
import argparse
import ast
import re
import sys
from pathlib import Path

import polib


ROOT = Path(__file__).resolve().parents[1]
SAAS = ROOT / "saas"
PO_PATH = SAAS / "locale/pt_BR/LC_MESSAGES/django.po"
MO_PATH = PO_PATH.with_suffix(".mo")
PLACEHOLDER = re.compile(r"%\([^)]+\)[a-z]")


def python_messages():
    messages = set()
    for path in SAAS.rglob("*.py"):
        if "migrations" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError) as exc:
            raise RuntimeError(f"No se pudo analizar {path}: {exc}") from exc
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "_"
                and node.args
            ):
                continue
            try:
                value = ast.literal_eval(node.args[0])
            except (ValueError, TypeError):
                continue
            if isinstance(value, str):
                messages.add(value)
    return messages


def template_messages():
    messages = set()
    trans_pattern = re.compile(
        r"{%\s*trans\s+([\"'])(.*?)\1(?:\s+[^%]*)?%}", re.DOTALL
    )
    block_pattern = re.compile(
        r"{%\s*blocktrans(?:\s+[^%]*)?%}(.*?){%\s*endblocktrans\s*%}",
        re.DOTALL,
    )
    variable_pattern = re.compile(r"{{\s*(\w+)(?:\|[^}]*)?\s*}}")
    for path in (SAAS / "templates").rglob("*"):
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        messages.update(match.group(2) for match in trans_pattern.finditer(content))
        for match in block_pattern.finditer(content):
            messages.add(
                variable_pattern.sub(r"%(\1)s", match.group(1)).strip()
            )
    return messages


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compile", action="store_true")
    args = parser.parse_args()
    catalog = polib.pofile(str(PO_PATH))
    entries = {entry.msgid: entry for entry in catalog if entry.msgid}
    expected = python_messages() | template_messages()
    missing = sorted(expected - entries.keys())
    untranslated = sorted(
        msgid for msgid in expected & entries.keys() if not entries[msgid].msgstr
    )
    bad_placeholders = sorted(
        msgid
        for msgid in expected & entries.keys()
        if set(PLACEHOLDER.findall(msgid))
        != set(PLACEHOLDER.findall(entries[msgid].msgstr))
    )
    if missing or untranslated or bad_placeholders:
        if missing:
            print("Faltan traducciones:\n- " + "\n- ".join(missing))
        if untranslated:
            print("Traducciones vacías:\n- " + "\n- ".join(untranslated))
        if bad_placeholders:
            print("Placeholders incompatibles:\n- " + "\n- ".join(bad_placeholders))
        return 1
    if args.compile:
        catalog.save_as_mofile(str(MO_PATH))
    print(
        f"Localización OK: {len(expected)} mensajes usados, "
        f"{catalog.percent_translated()}% del catálogo traducido."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
