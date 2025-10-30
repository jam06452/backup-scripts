#!/usr/bin/env python3
import ast
from pathlib import Path

TARGETS = [Path('backup.py'), Path('restore.py')]


def remove_docstrings(node):
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], 'value', None), ast.Constant) and isinstance(node.body[0].value.value, str):
            node.body.pop(0)
    for child in ast.iter_child_nodes(node):
        remove_docstrings(child)


for p in TARGETS:
    if not p.exists():
        print(f"Skipping {p}: not found")
        continue
    text = p.read_text(encoding='utf-8')
    shebang = ''
    lines = text.splitlines()
    if lines and lines[0].startswith('#!'):
        shebang = lines[0] + '\n'
    try:
        tree = ast.parse(text)
    except Exception as e:
        print(f"Failed to parse {p}: {e}")
        continue
    remove_docstrings(tree)
    try:
        new_code = ast.unparse(tree)
    except AttributeError:
        print('ast.unparse not available on this Python version')
        continue
    out = shebang + new_code + '\n'
    p.write_text(out, encoding='utf-8')
    print(f"Stripped comments/docstrings from {p}")
