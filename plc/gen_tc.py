"""Split MotionServer.st into the TwinCAT 3 PLC object files setup-csu.ps1 imports."""

from __future__ import annotations

import argparse
import re
import uuid
from pathlib import Path
from typing import Final

HERE: Final = Path(__file__).resolve().parent
SECTION: Final = re.compile(r"^// =+ (DUT|GVL|POU): (\w+).*$", re.MULTILINE)
HEADER: Final = ('<?xml version="1.0" encoding="utf-8"?>\n'
                 '<TcPlcObject Version="1.1.0.1" ProductVersion="3.1.4024.12">\n')
FOOTER: Final = "</TcPlcObject>\n"
EXTENSIONS: Final = {"DUT": "TcDUT", "GVL": "TcGVL", "POU": "TcPOU"}


def cdata(text: str) -> str:
    """Wrap text in a CDATA section."""
    return "<![CDATA[" + text.strip("\n") + "\n]]>"


def object_xml(kind: str, name: str, body: str) -> str:
    """Return one PLC object's XML element, with an id stable across runs."""
    object_id = "{" + str(uuid.uuid5(uuid.NAMESPACE_URL, f"lris2/csu-motion-server/{name}")) + "}"
    if kind == "GVL":
        declaration = cdata("{attribute 'qualified_only'}\n" + body)
        return (f'  <GVL Name="{name}" Id="{object_id}">\n'
                f"    <Declaration>{declaration}</Declaration>\n  </GVL>\n")
    if kind == "DUT":
        return (f'  <DUT Name="{name}" Id="{object_id}">\n'
                f"    <Declaration>{cdata(body)}</Declaration>\n  </DUT>\n")
    # The declaration runs to the last END_VAR before the body
    cut = body.rfind("END_VAR") + len("END_VAR\n")
    return (f'  <POU Name="{name}" Id="{object_id}" SpecialFunc="None">\n'
            f"    <Declaration>{cdata(body[:cut])}</Declaration>\n"
            f"    <Implementation>\n      <ST>{cdata(body[cut:])}</ST>\n"
            "    </Implementation>\n  </POU>\n")


def split(source: Path, out: Path) -> list[Path]:
    """Write one object file per section of ``source`` into ``out``."""
    parts = SECTION.split(source.read_text(encoding="utf-8"))
    written = []
    for kind, name, body in zip(parts[1::3], parts[2::3], parts[3::3]):
        path = out / f"{name}.{EXTENSIONS[kind]}"
        xml = object_xml(kind, name, body.strip("\n") + "\n")
        path.write_text(HEADER + xml + FOOTER, encoding="utf-8")
        written.append(path)
    return written


def main() -> None:
    """Parse arguments and regenerate the object files."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", nargs="?", type=Path, default=HERE / "MotionServer.st")
    parser.add_argument("out", nargs="?", type=Path, default=HERE / "csu-motion-server")
    args = parser.parse_args()
    for path in split(args.source, args.out):
        print(path.name)


if __name__ == "__main__":
    main()
