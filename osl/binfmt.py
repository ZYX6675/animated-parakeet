"""Generate binfmt_misc registrations so PE and Mach-O files launch through osl-open.

Deliberately NOT registered: universal (fat) Mach-O binaries. They begin with the same magic
bytes as Java class files (CAFEBABE) and binfmt_misc cannot tell them apart, so registering it
would hijack every Java class file. Launch those with osl-run directly.
Also note: a distribution's own Wine binfmt registration will conflict with the PE entry;
disable it when installing this one.
"""
from __future__ import annotations

INTERPRETER = "/usr/local/bin/osl-open"

# name -> (offset, magic as \\x escapes)
ENTRIES = {
    "osl-pe": (0, r"MZ"),
    "osl-macho64": (0, r"\xcf\xfa\xed\xfe"),
}


def registrations(interpreter: str = INTERPRETER) -> dict[str, str]:
    """Return {name: ':name:type:offset:magic:mask:interpreter:flags'} lines."""
    out = {}
    for name, (offset, magic) in ENTRIES.items():
        out[name] = f":{name}:M:{offset}:{magic}::{interpreter}:"
    return out


def conf_text(interpreter: str = INTERPRETER) -> str:
    return "\n".join(registrations(interpreter).values()) + "\n"


if __name__ == "__main__":
    print(conf_text(), end="")
