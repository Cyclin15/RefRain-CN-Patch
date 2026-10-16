# -*- coding: utf-8 -*-
"""
RefRain -prism memories-  Data.ra1 (.ra1/.rp1, "RAF1" format) archive tool.
Uses Unicorn to emulate the game's own transform routine (RefRain.exe 0x42a040)
so decryption/decompression matches the game exactly.

Layout knowledge (from reversing RefRain.exe, engine "RefRain System V1.03.7"):
  file header (18 bytes):
    +0x00 'RAF1'
    +0x04 mode | (seed << 4)      -> transform params for the trailer's first block
    +0x08 byte, +0x09 byte        -> trailer size key = (~h[9]) ^ h[8]
    +0x0A crc32(header with this field = 1000)
    +0x0E crc32(trailer)
  trailer (key bytes at EOF):
    transform(trailer, mode, seed, len=0x24) -> block1 (archive meta #1)
  block1 fields (at archive object +0x48):
    +0x48 type (1 = data.ra1, 0x10 = patch .rp1)
    +0x54 == 3
    +0x5C block2 offset, +0x60 block2 size, +0x64 crc, +0x68 mode|seed<<4
  block2 (0x2C bytes at object +0x12):
    +0x12 toc entry count
    +0x16 toc offset, +0x1A toc packed size, +0x1E crc, +0x22 mode|seed<<4
    +0x2A names offset, +0x2E names packed size, +0x32 names len, +0x36 crc, +0x3A mode|seed<<4
  TOC entry (40 bytes):
    +0x00 offset of filename inside names blob
    +0x04 crc32(lowercased filename)
    +0x08 packed size, +0x0C raw size
    +0x1C absolute data offset
    +0x20 mode | (seed << 4)
    +0x24 crc32(packed data)
"""
import struct
import zlib
from unicorn import *
from unicorn.x86_const import *

EXE = r"D:\Steam\steamapps\common\RefRain - prism memories -\RefRain.exe"
BASE = 0x400000
TRANSFORM = 0x42A040   # dispatch: mode/seed from globals 0x5afa94/0x5afb98
MALLOC = 0x469AC6
FREE = 0x469AC1
G_MODE = 0x5AFA94
G_SEED = 0x5AFB98

STACK = 0x00100000
STACK_SZ = 0x00100000          # 1 MB
SCRATCH = 0x20000000           # src buffers
SCRATCH_SZ = 0x08000000        # 128 MB
HEAP = 0x30000000              # emulated malloc arena
HEAP_SZ = 0x08000000           # 128 MB
MAGIC_RET = 0x70000000


class RefRainEmu(object):
    def __init__(self, exe_path=EXE):
        import pefile
        pe = pefile.PE(exe_path)
        self.img = pe.get_memory_mapped_image()
        self.uc = Uc(UC_ARCH_X86, UC_MODE_32)
        size = (len(self.img) + 0xFFF) & ~0xFFF
        self.uc.mem_map(BASE, size)
        self.uc.mem_write(BASE, bytes(self.img))
        self.uc.mem_map(STACK, STACK_SZ)
        self.uc.mem_map(SCRATCH, SCRATCH_SZ)
        self.uc.mem_map(HEAP, HEAP_SZ)
        self.uc.mem_map(MAGIC_RET, 0x1000)
        self.uc.mem_write(MAGIC_RET, b"\xc3" * 16)
        self.heap_ptr = HEAP + 0x10000
        self.scratch_ptr = SCRATCH + 0x10000
        self.uc.hook_add(UC_HOOK_CODE, self._hook_malloc, begin=MALLOC, end=MALLOC)
        self.uc.hook_add(UC_HOOK_CODE, self._hook_free, begin=FREE, end=FREE)

    # -- emulated CRT new/delete (cdecl) ------------------------------------
    def _hook_malloc(self, uc, address, size, user):
        n = struct.unpack("<I", uc.mem_read(uc.reg_read(UC_X86_REG_ESP) + 4, 4))[0]
        ptr = self.heap_ptr
        self.heap_ptr = (self.heap_ptr + n + 0x40) & ~0xF
        uc.reg_write(UC_X86_REG_EAX, ptr)
        esp = uc.reg_read(UC_X86_REG_ESP)
        eip = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        uc.reg_write(UC_X86_REG_ESP, esp + 4)
        uc.reg_write(UC_X86_REG_EIP, eip)

    def _hook_free(self, uc, address, size, user):
        esp = uc.reg_read(UC_X86_REG_ESP)
        eip = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        uc.reg_write(UC_X86_REG_ESP, esp + 4)
        uc.reg_write(UC_X86_REG_EIP, eip)

    # -- the game's transform dispatcher ------------------------------------
    def transform(self, mode, seed, src, length, edx_val=1):
        """Run RefRain.exe!0x42a040(mode, seed, src, length) -> bytes."""
        assert len(src) > 0
        # reset bump heap: callers copy the result out immediately after
        # emu_start returns, so no pointer survives across calls.
        self.heap_ptr = HEAP + 0x10000
        # place src in scratch
        if self.scratch_ptr + len(src) + 0x1000 > SCRATCH + SCRATCH_SZ:
            self.scratch_ptr = SCRATCH + 0x10000
        src_addr = self.scratch_ptr
        self.scratch_ptr += (len(src) + 0x100) & ~0xF
        self.uc.mem_write(src_addr, src)
        # globals: mode / seed
        self.uc.mem_write(G_MODE, struct.pack("<I", mode & 0xFFFFFFFF))
        self.uc.mem_write(G_SEED, struct.pack("<I", seed & 0xFFFFFFFF))
        # cdecl call: push out(0), push length, call
        esp = STACK + STACK_SZ - 0x1000
        self.uc.mem_write(esp + 0, struct.pack("<I", MAGIC_RET))
        self.uc.mem_write(esp + 4, struct.pack("<I", length))
        self.uc.mem_write(esp + 8, struct.pack("<I", 0))          # out = NULL -> internal malloc
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        self.uc.reg_write(UC_X86_REG_ECX, src_addr)
        self.uc.reg_write(UC_X86_REG_EDX, edx_val)
        self.uc.emu_start(TRANSFORM, MAGIC_RET, timeout=0, count=0)
        out_ptr = self.uc.reg_read(UC_X86_REG_EAX)
        if out_ptr == 0:
            return None
        return bytes(self.uc.mem_read(out_ptr, length))


class Ra1Archive(object):
    def __init__(self, path, emu=None, expect_type=1):
        self.path = path
        self.f = open(path, "rb")
        self.data = self.f.read()
        self.f.close()
        self.emu = emu or RefRainEmu()
        self._parse(expect_type)

    def _read_at(self, off, size):
        return self.data[off:off + size]

    @staticmethod
    def _crc(data, expect, what):
        got = zlib.crc32(data) & 0xFFFFFFFF
        if expect is not None and got != expect:
            raise ValueError("crc mismatch on %s: got %08x want %08x" % (what, got, expect))

    def _parse(self, expect_type):
        d = self.data
        h = bytearray(d[:18])
        if bytes(h[:4]) != b"RAF1":
            raise ValueError("not a RAF1 archive")
        crc_hdr = struct.unpack("<I", bytes(h[0x0A:0x0E]))[0]
        h[0x0A:0x0E] = struct.pack("<I", 1000)
        self._crc(bytes(h), crc_hdr, "header")
        key = ((~h[9]) & 0xFF) ^ h[8]
        trailer = d[len(d) - key:] if key else b""
        self._crc(trailer, struct.unpack("<I", bytes(h[0x0E:0x12]))[0], "trailer")

        h4 = struct.unpack("<I", bytes(d[4:8]))[0]
        mode, seed = h4 & 0xF, h4 >> 4

        # block1 (0x24 bytes) from the trailer
        b1 = self.emu.transform(mode, seed, trailer, 0x24)
        type_, v1, v2, three, v4, b2_off, b2_size, b2_crc, b2_flags = struct.unpack(
            "<9I", b1[:0x24])
        if type_ != expect_type:
            raise ValueError("archive type %d, expected %d" % (type_, expect_type))
        if three != 3:
            raise ValueError("block1 magic != 3")
        self.type = type_

        # block2 (0x2C bytes) from the middle of the file
        b2raw = self._read_at(b2_off, b2_size)
        self._crc(b2raw, b2_crc, "block2")
        b2 = self.emu.transform(b2_flags & 0xF, b2_flags >> 4, b2raw, 0x2C)
        (self.count, toc_off, toc_psize, toc_crc, toc_flags,
         unk, names_off, names_psize, names_len, names_crc, names_flags) = struct.unpack(
            "<11I", b2[:0x2C])

        # names blob
        names_raw = self._read_at(names_off, names_psize)
        self._crc(names_raw, names_crc, "names")
        self.names = self.emu.transform(names_flags & 0xF, names_flags >> 4,
                                        names_raw, names_len, edx_val=names_psize)

        # TOC
        toc_raw = self._read_at(toc_off, toc_psize)
        self._crc(toc_raw, toc_crc, "toc")
        toc = self.emu.transform(toc_flags & 0xF, toc_flags >> 4,
                                 toc_raw, self.count * 40, edx_val=toc_psize)
        self.entries = []
        for i in range(self.count):
            e = toc[i * 40:(i + 1) * 40]
            (name_off, name_crc, psize, rsize, u10, u14, u18,
             data_off, flags, pcrc) = struct.unpack("<10I", e)
            end = self.names.index(b"\x00", name_off) if name_off < len(self.names) else name_off
            name = self.names[name_off:end].decode("cp932", "replace")
            self.entries.append(dict(
                name=name, name_crc=name_crc, psize=psize, rsize=rsize,
                data_off=data_off, flags=flags, pcrc=pcrc,
                mode=flags & 0xF, seed=flags >> 4))

    def entry_by_name(self, name):
        want = zlib.crc32(name.lower().encode("ascii", "replace")) & 0xFFFFFFFF
        for e in self.entries:
            if e["name_crc"] == want:
                return e
        return None

    def read(self, e):
        raw = self._read_at(e["data_off"], e["psize"])
        self._crc(raw, e["pcrc"], "file %s" % e["name"])
        return self.emu.transform(e["mode"], e["seed"], raw, e["rsize"],
                                  edx_val=e["psize"])


if __name__ == "__main__":
    import sys, io, os
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    arch = Ra1Archive(r"D:\Steam\steamapps\common\RefRain - prism memories -\Data\Data.ra1")
    print("type:", arch.type, "entries:", arch.count)
    modes = {}
    for e in arch.entries:
        modes[e["mode"]] = modes.get(e["mode"], 0) + 1
    print("mode histogram:", modes)
    # show first entries + all script/text files
    for e in arch.entries[:10]:
        print("  %-50s psize=%-9d rsize=%-9d mode=%d" % (e["name"], e["psize"], e["rsize"], e["mode"]))
    print("...")
    for e in arch.entries:
        n = e["name"].lower()
        if n.endswith((".rsr", ".rsd", ".txt")) or "script" in n or "local" in n:
            print("  TEXT %-46s psize=%-9d rsize=%-9d mode=%d" % (e["name"], e["psize"], e["rsize"], e["mode"]))
