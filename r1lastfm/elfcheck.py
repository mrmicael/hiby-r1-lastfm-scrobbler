"""Decide whether a binary is a static MIPS little-endian executable.

This is the gate in front of everything that runs on the device, so it is done by reading
the ELF header rather than by shelling out to ``file`` — which does not exist on
Windows and, on the machines where it does, reports MIPS variants in wording
that changes between versions.

What matters for the R1:

* 32-bit (``EI_CLASS`` = 1) — the Ingenic X1600 is MIPS32.
* Little-endian (``EI_DATA`` = 1) — mips**el**. A big-endian build is the single
  easiest mistake to make, because most prebuilt "mips" binaries are big-endian
  and the file command's output differs by one word.
* ``e_machine`` = 8 (EM_MIPS).
* No ``PT_INTERP`` segment. A dynamic binary needs an interpreter and the
  device's libraries, which is exactly what a supplied curl will not have.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field

from .idioma import t

EM_MIPS = 8
ET_EXEC = 2
ET_DYN = 3
PT_INTERP = 3
PT_DYNAMIC = 2
DT_NEEDED = 1
DT_STRTAB = 5
DT_SONAME = 14

EF_MIPS_ABI_O32 = 0x00001000
EF_MIPS_ARCH_MASK = 0xF0000000


@dataclass
class ElfReport:
    path: str
    is_elf: bool = False
    bits: int = 0
    endian: str = ""
    machine: int = 0
    machine_name: str = ""
    etype: int = 0
    static: bool = False
    interp: str = ""
    needed: list[str] = field(default_factory=list)
    size: int = 0
    problems: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    linkage_known: bool = False
    soname: str = ""

    @property
    def is_library(self) -> bool:
        """A shared object, not a program.

        Told apart by DT_SONAME. It matters: a .so is *expected* to be dynamic
        and to list DT_NEEDED entries, whereas for the curl binary either of
        those is disqualifying.
        """
        return bool(self.soname)

    @property
    def acceptable(self) -> bool:
        return self.is_elf and not self.problems

    def summary(self) -> str:
        if not self.is_elf:
            return t("elf.not_elf")
        arch = f"{self.bits} bits, {self.endian}, {self.machine_name}"
        if not self.linkage_known:
            link = t("elf.link.unknown")
        elif self.is_library:
            link = t("elf.link.library", soname=self.soname)
        elif self.static:
            link = t("elf.link.static")
        else:
            link = t("elf.link.dynamic",
                     interp=self.interp or t("elf.interp.unnamed"))
        out = [f"{arch} — {link}", f"{self.size:,} bytes"]
        if self.needed:
            rotulo = (t("elf.libs.used") if self.is_library
                      else t("elf.libs.needed"))
            out.append(f"{rotulo}: " + ", ".join(self.needed))
        return "  ·  ".join(out)


_MACHINES = {
    3: "x86", 8: "MIPS", 40: "ARM", 62: "x86-64", 183: "AArch64",
    20: "PowerPC", 21: "PowerPC64", 243: "RISC-V", 22: "S390",
}


def inspect_elf(path: str) -> ElfReport:
    rep = ElfReport(path=path)
    try:
        with open(path, "rb") as fh:
            blob = fh.read()
    except OSError as exc:
        rep.problems.append(t("elf.err.read", erro=exc))
        return rep

    rep.size = len(blob)
    if len(blob) < 52 or blob[:4] != b"\x7fELF":
        rep.problems.append(t("elf.err.signature"))
        return rep

    rep.is_elf = True
    ei_class, ei_data = blob[4], blob[5]
    rep.bits = {1: 32, 2: 64}.get(ei_class, 0)
    rep.endian = {1: "little-endian", 2: "big-endian"}.get(
        ei_data, t("elf.endian.unknown"))

    if ei_class != 1:
        rep.problems.append(t("elf.err.bits", bits=rep.bits or "?"))
    if ei_data != 1:
        rep.problems.append(t("elf.err.endian"))

    end = "<" if ei_data == 1 else ">"
    try:
        (rep.etype, rep.machine) = struct.unpack_from(end + "HH", blob, 16)
    except struct.error:
        rep.problems.append(t("elf.err.truncated"))
        return rep

    rep.machine_name = _MACHINES.get(
        rep.machine, t("elf.machine.unknown", numero=rep.machine))
    if rep.machine != EM_MIPS:
        rep.problems.append(t("elf.err.machine", maquina=rep.machine_name))

    if ei_class != 1:
        return rep  # the 64-bit header layout differs; nothing more to say

    try:
        e_flags, = struct.unpack_from(end + "I", blob, 0x24)
        e_phoff, = struct.unpack_from(end + "I", blob, 0x1C)
        e_phentsize, e_phnum = struct.unpack_from(end + "HH", blob, 0x2A)
    except struct.error:
        rep.problems.append(t("elf.err.truncated"))
        return rep

    if rep.machine == EM_MIPS and not (e_flags & EF_MIPS_ABI_O32):
        rep.notes.append(t("elf.note.abi"))

    rep.static = True
    rep.linkage_known = True
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        if off + 32 > len(blob):
            break
        p_type, p_offset, _vaddr, _paddr, p_filesz = struct.unpack_from(
            end + "IIIII", blob, off
        )
        if p_type == PT_INTERP:
            rep.static = False
            raw = blob[p_offset:p_offset + p_filesz]
            rep.interp = raw.split(b"\x00")[0].decode("utf-8", "replace")
        elif p_type == PT_DYNAMIC:
            needed, soname = _read_dynamic(blob, end, p_offset, p_filesz)
            rep.needed.extend(needed)
            rep.soname = rep.soname or soname

    if rep.is_library:
        # Nothing more to complain about: a shared object is supposed to be
        # dynamic and to name the libraries it uses. Whether it is the *right*
        # library for this device is a question of architecture, checked above.
        rep.notes.append(t("elf.note.library"))
        return rep

    if not rep.static:
        rep.problems.append(t(
            "elf.err.dynamic",
            interp=rep.interp or t("elf.interp.unknown")))
    if rep.needed:
        rep.problems.append(t("elf.err.needs", libs=", ".join(rep.needed)))
    if rep.etype not in (ET_EXEC, ET_DYN):
        rep.problems.append(t("elf.err.etype", tipo=rep.etype))
    if rep.etype == ET_DYN and rep.static:
        rep.notes.append(t("elf.note.pie"))

    if rep.acceptable and rep.size < 200_000:
        rep.notes.append(t("elf.note.small", bytes=f"{rep.size:,}"))
    return rep


def _read_dynamic(blob: bytes, end: str, offset: int,
                  size: int) -> tuple[list[str], str]:
    """Read DT_NEEDED names and DT_SONAME out of .dynamic.

    Returns (needed, soname). The soname is what distinguishes a shared
    library from a program, which changes how the result should be judged.
    """
    out: list[str] = []
    entries = []
    pos = offset
    while pos + 8 <= min(offset + size, len(blob)):
        tag, val = struct.unpack_from(end + "iI", blob, pos)
        if tag == 0:
            break
        entries.append((tag, val))
        pos += 8

    strtab = next((v for tag, v in entries if tag == DT_STRTAB), None)
    if strtab is None:
        count = sum(1 for tag, _ in entries if tag == DT_NEEDED)
        return ([t("elf.libs.count", n=count)] if count else []), ""

    # Map the vaddr back through the PT_LOAD segments.
    try:
        e_phoff, = struct.unpack_from(end + "I", blob, 0x1C)
        e_phentsize, e_phnum = struct.unpack_from(end + "HH", blob, 0x2A)
    except struct.error:
        return [], ""
    file_off = None
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        if off + 20 > len(blob):
            break
        p_type, p_offset, p_vaddr, _p, p_filesz = struct.unpack_from(end + "IIIII", blob, off)
        if p_type == 1 and p_vaddr <= strtab < p_vaddr + p_filesz:
            file_off = p_offset + (strtab - p_vaddr)
            break
    if file_off is None:
        return [], ""

    def name_at(val: int) -> str:
        start = file_off + val
        if 0 <= start < len(blob):
            raw = blob[start:start + 256].split(b"\x00")[0]
            return raw.decode("utf-8", "replace")
        return ""

    soname = ""
    for tag, val in entries:
        if tag == DT_NEEDED:
            got = name_at(val)
            if got:
                out.append(got)
        elif tag == DT_SONAME:
            soname = name_at(val)
    return out, soname


def describe_for_user(rep: ElfReport) -> str:
    """A short verdict plus the reasons, ready to drop into a label."""
    if rep.acceptable:
        head = (t("elf.ok.library") if rep.is_library else t("elf.ok.program"))
        tail = "\n".join(t("elf.note.prefix") + n for n in rep.notes)
        return head + ("\n" + tail if tail else "")
    return t("elf.refused") + "\n" + "\n".join("• " + p for p in rep.problems)


def check_curl(path: str) -> ElfReport:
    """The curl gate: must be a static *program*, never a library."""
    rep = inspect_elf(path)
    if rep.is_elf and rep.is_library:
        rep.problems.append(t("elf.err.is_library", soname=rep.soname))
    return rep
