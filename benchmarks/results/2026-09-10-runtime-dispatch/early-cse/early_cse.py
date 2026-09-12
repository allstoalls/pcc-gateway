"""Conservative local value reuse for the owned text pipeline.

Tables are scoped to a basic block. Memory entries require an exact scalar
type and address; every unrecognized/effectful instruction invalidates them.
Atomic and volatile operations are never forwarded or eliminated.
"""

import re

from .instcombine import _split_functions
from .instsimplify import simplify_module_text
from .text_tokens import replace_local_names

_NAME = r"[A-Za-z_.$-][A-Za-z0-9_.$-]*"
_VALUE = r"(?:%" + _NAME + r"|@" + _NAME + r"|-?[0-9]+|true|false|null)"
_PTR = r"(?:%|@)" + _NAME
_ASSIGN = re.compile(r"^\s*%(" + _NAME + r")\s*=\s*(.+?)\s*$")
_LABEL = re.compile(r'^(?:[-\w.$]+|"(?:[^"\\]|\\.)*"):\s*(?:;.*)?$')
_LOAD = re.compile(r"^load (i[1-9][0-9]*|ptr), ptr (" + _PTR + r")((?:, align [0-9]+)?)$")
_STORE = re.compile(r"^store (i[1-9][0-9]*|ptr) (" + _VALUE + r"), ptr (" + _PTR + r")((?:, align [0-9]+)?)$")
_ALIAS = re.compile(r"^bitcast ptr (" + _PTR + r") to ptr$")
_COMMUTE = re.compile(r"^(add|mul|and|or|xor)((?: (?:nsw|nuw|exact|disjoint))*) (i[1-9][0-9]*) (" + _VALUE + r"), (" + _VALUE + r")$")
_PURE = {
    "add", "sub", "mul", "and", "or", "xor", "shl", "lshr", "ashr",
    "icmp", "select", "getelementptr", "bitcast", "zext", "sext", "trunc",
    "extractvalue", "insertvalue",
}


def _expression_key(rhs: str) -> str:
    match = _COMMUTE.fullmatch(rhs)
    if match is None:
        return rhs
    op, flags, ty, lhs, right = match.groups()
    if right < lhs:
        lhs, right = right, lhs
    return op + flags + " " + ty + " " + lhs + ", " + right


def _rewrite_function(text: str) -> tuple[str, bool]:
    # Removing numbered unnamed values would require renumbering the function.
    if re.search(r"^\s*%[0-9]+\s*=", text, re.MULTILINE):
        return text, False
    replacements: dict[str, str] = {}
    expressions: dict[str, str] = {}
    loads: dict[str, str] = {}
    stores: dict[str, str] = {}
    output: list[str] = []
    for original in text.splitlines(keepends=True):
        line = replace_local_names(original, replacements)
        stripped = line.strip()
        if stripped.startswith("define ") or stripped == "}" or _LABEL.fullmatch(stripped):
            expressions.clear()
            loads.clear()
            stores.clear()
            output.append(line)
            continue
        if not stripped or stripped.startswith(";"):
            output.append(line)
            continue
        assigned = _ASSIGN.fullmatch(stripped)
        rhs = assigned.group(2) if assigned is not None else stripped
        opcode = rhs.split(" ", 1)[0]
        # No reuse of undef choices, atomic reads, volatile reads or metadata
        # whose exact effects this scalar subset has not modeled.
        uncertain = bool(re.search(r"\b(?:undef|poison|atomic|volatile)\b|!|;", rhs))
        if assigned is not None and not uncertain:
            result = assigned.group(1)
            alias = _ALIAS.fullmatch(rhs)
            if alias is not None:
                replacements[result] = alias.group(1)
                continue
            load = _LOAD.fullmatch(rhs)
            if load is not None:
                ty, pointer, _alignment = load.groups()
                stored = stores.get(ty + " " + pointer)
                previous = stored if stored is not None else loads.get(rhs)
                if previous is not None:
                    replacements[result] = previous
                    continue
                loads[rhs] = "%" + result
                output.append(line)
                continue
            if opcode in _PURE:
                key = _expression_key(rhs)
                previous = expressions.get(key)
                if previous is not None:
                    replacements[result] = previous
                    continue
                expressions[key] = "%" + result
                output.append(line)
                continue
        loads.clear()
        stores.clear()
        stored = _STORE.fullmatch(rhs) if not uncertain else None
        if stored is not None:
            ty, value, pointer, _alignment = stored.groups()
            stores[ty + " " + pointer] = value
        output.append(line)
    if not replacements:
        return text, False
    # A PHI in an earlier textual block can reference a later definition.
    rewritten = replace_local_names("".join(output), replacements)
    return rewritten, True


def early_cse_text(text: str) -> tuple[str, bool]:
    output: list[str] = []
    changed = False
    for is_function, chunk in _split_functions(text):
        if is_function:
            chunk, local_changed = _rewrite_function(chunk)
            if local_changed:
                chunk, _ = simplify_module_text(chunk)
                changed = True
        output.append(chunk)
    return ("".join(output), True) if changed else (text, False)
