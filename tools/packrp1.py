# -*- coding: utf-8 -*-
"""
Build a RefRain patch archive (Patch/patch_NNNN.rp1, "RAF1" format, type 0x10)
and verify it with the game's own loader code under Unicorn.

Everything (metadata blocks + file payloads) is stored with transform mode 0
(plain memcpy), which the game's dispatcher (RefRain.exe 0x42a040) accepts.
Requirements discovered from the registry loader (RefRain.exe 0x42a2f0):
  block1.type (obj+0x48) must equal 0x10 for patches (Data.ra1 uses 1)
  block1.v1   (obj+0x4C) must equal the engine version global (0x3e8, like Data.ra1)
  block1.three(obj+0x54) must be 3 (checked by the archive opener 0x428980)
  block1.v4   (obj+0x58) is used together with toc_crc for duplicate detection
"""
import struct
import zlib

BLOCK1 = 0x24   # 9 dwords
BLOCK2 = 0x2C   # 11 dwords
TOC_ENT = 40

# values copied from Data.ra1
V1 = 0x3E8          # engine version stamp
V4 = 0x67A7596A     # archive identity stamp (only used for dedup)


def build_rp1(files):
    """files: dict[name(str) -> bytes]; returns rp1 archive bytes (type 0x10)."""
    names = [n.encode("ascii") for n in files]      # keep insertion order
    names_blob = b"".join(n + b"\0" for n in names)
    count = len(names)

    # --- plan layout: header | block2 | toc | names | payloads | trailer(block1)
    b2_off = 18
    toc_off = b2_off + BLOCK2
    names_off = toc_off + count * TOC_ENT
    data_off = names_off + len(names_blob)

    toc = b""
    payload = b""
    name_ptr = 0
    for n, content in zip(names, files.values()):
        e_name = name_ptr
        e_ncrc = zlib.crc32(n.lower()) & 0xFFFFFFFF
        e_psize = e_rsize = len(content)
        e_off = data_off + len(payload)
        e_flags = 0            # mode 0, seed 0 -> plain memcpy
        e_pcrc = zlib.crc32(content) & 0xFFFFFFFF
        toc += struct.pack("<10I", e_name, e_ncrc, e_psize, e_rsize,
                           0, 0, 0, e_off, e_flags, e_pcrc)
        payload += content
        name_ptr += len(n) + 1

    # block2: count, toc_off, toc_psize, toc_crc, toc_flags, unk, names_off,
    #         names_psize, names_len, names_crc, names_flags
    toc_crc = zlib.crc32(toc) & 0xFFFFFFFF
    names_crc = zlib.crc32(names_blob) & 0xFFFFFFFF
    b2 = struct.pack("<11I", count, toc_off, len(toc), toc_crc, 0, 0x12,
                     names_off, len(names_blob), len(names_blob), names_crc, 0)
    assert len(b2) == BLOCK2

    # --- trailer = block1 (plain): type, v1, v2, three, v4,
    #     b2_off, b2_size, b2_crc, b2_flags
    trailer = struct.pack("<9I", 0x10, V1, V1, 3, V4,
                          b2_off, BLOCK2, zlib.crc32(b2) & 0xFFFFFFFF, 0)
    assert len(trailer) == BLOCK1
    # trailer key byte: ((~h9)&0xff)^h8 == len(trailer) -> h8=0x24, h9=0xff
    h8, h9 = BLOCK1, 0xFF
    assert (((~h9) & 0xFF) ^ h8) == BLOCK1

    body = b"".join([b2, toc, names_blob, payload])
    total = 18 + len(body) + BLOCK1

    hdr = bytearray(18)
    hdr[0:4] = b"RAF1"
    struct.pack_into("<I", hdr, 4, 0)     # mode 0 | seed 0
    hdr[8] = h8
    hdr[9] = h9
    struct.pack_into("<I", hdr, 0x0A, 1000)
    struct.pack_into("<I", hdr, 0x0E, zlib.crc32(trailer) & 0xFFFFFFFF)
    crc_hdr = zlib.crc32(bytes(hdr)) & 0xFFFFFFFF
    struct.pack_into("<I", hdr, 0x0A, crc_hdr)

    return bytes(hdr) + body + trailer


# ----------------------------------------------------------------------------
#  Verification: run the game's own registry loader / archive opener / file
#  loader under Unicorn, hooking only the statically-linked CRT I/O helpers.
# ----------------------------------------------------------------------------
try:  # 模拟验证部分依赖 unicorn; 仅打包(build_rp1)时可缺
    from unicorn import *
    from unicorn.x86_const import *
    from raf1 import RefRainEmu, STACK, STACK_SZ, HEAP, MAGIC_RET
except ImportError:
    RefRainEmu = None

GAME_DIR = r"D:\Steam\steamapps\common\RefRain - prism memories -"

FOPEN = 0x471763
FREAD = 0x471A5B
FSEEK = 0x471E52
FCLOSE = 0x4717F1
STRLWR = 0x4720A7
STRDUP = 0x472014
STRICMP = 0x472134
STRNCMP = 0x472210
CRTFREE = 0x471E6D          # CRT free() (used by the archive lookup on strdup'd strings)
DBGLOG = 0x4286F0
PATHFIX = 0x437BB0
LOAD_ARCHIVE = 0x42A2F0      # thiscall(ecx=path, edx=expected_type)
LOAD_FILE = 0x42A5E0         # cdecl(ecx=name, edx=out_buf(0=malloc), stack=&size)
G_ARCH_COUNT = 0x5AFBA0
G_ARCH_VER = 0x5AFB9C
CREATEFILEA_IAT = 0x490150

STUB = 0x70000010            # "return -1" stub for CreateFileA


class GameFileEmu(RefRainEmu):
    """RefRain.exe image + hooked CRT file/string functions, so the game's own
    archive code can run against real files on disk."""

    def __init__(self):
        RefRainEmu.__init__(self)
        import os
        self.os = os
        self.files = {}          # fake FILE* -> python file object
        self.next_handle = 0x60000000
        self.logs = []
        # CreateFileA fallback stub: mov eax,-1 ; ret 0x1c
        self.uc.mem_write(STUB, b"\xb8\xff\xff\xff\xff\xc2\x1c\x00")
        self.uc.mem_write(CREATEFILEA_IAT, struct.pack("<I", STUB))
        for a in (FOPEN, FREAD, FSEEK, FCLOSE, STRLWR, STRDUP, STRICMP,
                  STRNCMP, CRTFREE, DBGLOG, PATHFIX):
            self.uc.hook_add(UC_HOOK_CODE, self._dispatch, begin=a, end=a)

    # -- helpers -------------------------------------------------------------
    def _ret(self, uc, eax, nargs=0):
        # All hooked CRT helpers are __cdecl (callers clean up with add esp),
        # so pop only the return address.
        esp = uc.reg_read(UC_X86_REG_ESP)
        eip = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        uc.reg_write(UC_X86_REG_ESP, esp + 4)
        uc.reg_write(UC_X86_REG_EIP, eip)
        uc.reg_write(UC_X86_REG_EAX, eax & 0xFFFFFFFF)

    def _ret_this(self, uc, eax):
        esp = uc.reg_read(UC_X86_REG_ESP)
        eip = struct.unpack("<I", uc.mem_read(esp, 4))[0]
        uc.reg_write(UC_X86_REG_ESP, esp + 4)
        uc.reg_write(UC_X86_REG_EIP, eip)
        uc.reg_write(UC_X86_REG_EAX, eax & 0xFFFFFFFF)

    def _cstr(self, uc, addr):
        out = b""
        while True:
            c = bytes(uc.mem_read(addr, 1))
            if c == b"\0":
                return out
            out += c
            addr += 1

    def _dispatch(self, uc, address, size, user):
        esp = uc.reg_read(UC_X86_REG_ESP)
        arg = lambda i: struct.unpack("<I", uc.mem_read(esp + 4 + 4 * i, 4))[0]

        if address == FOPEN:                          # fopen(path, mode)
            path = self._cstr(uc, arg(0))
            full = self.os.path.join(GAME_DIR, path.decode("mbcs"))
            try:
                f = open(full, "rb")
            except OSError:
                self._ret(uc, 0, 2)
                return
            h = self.next_handle
            self.next_handle += 4
            self.files[h] = f
            self._ret(uc, h, 2)

        elif address == FREAD:                        # fread(buf, sz, n, fp)
            buf, sz, n, fp = arg(0), arg(1), arg(2), arg(3)
            total = sz * n
            data = self.files[fp].read(total) if fp in self.files else b""
            uc.mem_write(buf, data)
            self._ret(uc, len(data) // sz if sz else 0, 4)

        elif address == FSEEK:                        # fseek(fp, off, whence)
            fp, off, wh = arg(0), struct.unpack("<i", uc.mem_read(esp + 8, 4))[0], arg(2)
            if fp in self.files:
                self.files[fp].seek(off, wh)
            self._ret(uc, 0, 3)

        elif address == FCLOSE:                       # fclose(fp)
            fp = arg(0)
            if fp in self.files:
                self.files[fp].close()
                del self.files[fp]
            self._ret(uc, 0, 1)

        elif address == STRLWR:                       # strlwr(s) cdecl
            s = arg(0)
            low = self._cstr(uc, s).lower()
            uc.mem_write(s, low + b"\0")
            self._ret(uc, s, 1)

        elif address == STRDUP:                       # strdup(s) cdecl
            s = self._cstr(uc, arg(0))
            ptr = self.heap_ptr
            self.heap_ptr = (self.heap_ptr + len(s) + 1 + 0x10) & ~0xF
            uc.mem_write(ptr, s + b"\0")
            self._ret(uc, ptr, 1)

        elif address == STRICMP:                      # stricmp(a, b) cdecl
            a = self._cstr(uc, arg(0)).lower()
            b = self._cstr(uc, arg(1)).lower()
            self._ret(uc, (a > b) - (a < b), 2)

        elif address == STRNCMP:                      # strncmp(a, b, n) cdecl
            a = self._cstr(uc, arg(0))
            b = self._cstr(uc, arg(1))
            n = arg(2)
            self._ret(uc, (a[:n] > b[:n]) - (a[:n] < b[:n]), 3)

        elif address == CRTFREE:                      # CRT free(ptr): no-op (bump heap)
            self._ret(uc, 0, 1)

        elif address == DBGLOG:                       # debug log: swallow
            self.logs.append(address)
            self._ret(uc, 0, 0)

        elif address == PATHFIX:                      # path fixer: copy through
            src = uc.reg_read(UC_X86_REG_ECX)
            dst = uc.reg_read(UC_X86_REG_EDX)
            s = self._cstr(uc, src)
            uc.mem_write(dst, s + b"\0")
            self._ret_this(uc, dst)

    # -- game API ------------------------------------------------------------
    def load_archive(self, path, expected_type):
        """Run the game's registry loader 0x42a2f0(path, expected_type).

        NOTE: heap must NOT be reset here -- the archive registry keeps
        TOC/names buffers on the emulated heap across calls."""
        p = self.heap_ptr
        self.heap_ptr += 0x100
        self.uc.mem_write(p, path.encode("ascii") + b"\0")
        esp = STACK + STACK_SZ - 0x2000
        self.uc.mem_write(esp, struct.pack("<I", MAGIC_RET))
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        self.uc.reg_write(UC_X86_REG_ECX, p)
        self.uc.reg_write(UC_X86_REG_EDX, expected_type)
        self.uc.emu_start(LOAD_ARCHIVE, MAGIC_RET, timeout=0, count=0)
        al = self.uc.reg_read(UC_X86_REG_EAX) & 0xFF
        count = struct.unpack("<I", self.uc.mem_read(G_ARCH_COUNT, 4))[0]
        return al, count

    def load_file(self, name):
        """Run the game's file loader 0x42a5e0(name, out=0, &size) -> bytes.

        NOTE: heap must NOT be reset -- the archive registry still holds
        its TOC/names buffers, resetting would hand out overlapping memory."""
        p = self.heap_ptr
        self.heap_ptr += 0x100
        self.uc.mem_write(p, name.encode("ascii") + b"\0")
        sp = self.heap_ptr
        self.heap_ptr += 0x100
        self.uc.mem_write(sp, struct.pack("<I", 0))
        esp = STACK + STACK_SZ - 0x2000
        self.uc.mem_write(esp + 0, struct.pack("<I", MAGIC_RET))
        self.uc.mem_write(esp + 4, struct.pack("<I", sp))
        self.uc.reg_write(UC_X86_REG_ESP, esp)
        self.uc.reg_write(UC_X86_REG_ECX, p)
        self.uc.reg_write(UC_X86_REG_EDX, 0)
        self.uc.emu_start(LOAD_FILE, MAGIC_RET, timeout=0, count=0)
        buf = self.uc.reg_read(UC_X86_REG_EAX)
        if not buf:
            return None, 0
        size = struct.unpack("<I", self.uc.mem_read(sp, 4))[0]
        return bytes(self.uc.mem_read(buf, size)), size


if __name__ == "__main__":
    import sys, io, os
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    # 1) build a test patch: localization.rsr with a marker line swapped in
    orig = open(os.path.join(GAME_DIR, "Data", "Data.ra1"), "rb").read()  # noqa
    from raf1 import Ra1Archive
    base = Ra1Archive(os.path.join(GAME_DIR, "Data", "Data.ra1"))
    e = base.entry_by_name("Data/Script/localization.rsr")
    l10n = base.read(e)
    marker = b"[CN-PATCH-OK] Prism Memories Chinese Patch Test Line"
    test = l10n.replace(b"RefRain \x81\x60prism memories\x81\x60 (Web Trial Ver.)",
                        marker, 1)
    # also swap the English title lines (window title, Language=1)
    test = test.replace(b"RefRain -prism memories- (The web trial version)",
                        b"[CN-PATCH-OK] Window Title Test", 1)
    test = test.replace(b"RefRain -prism memories-",
                        b"[CN-PATCH-OK] RefRain", 1)
    assert test != l10n, "marker substitution failed"

    files = {"Data/Script/localization.rsr": test}
    rp1 = build_rp1(files)
    patch_dir = os.path.join(GAME_DIR, "Patch")
    if not os.path.isdir(patch_dir):
        os.makedirs(patch_dir)
    out = os.path.join(patch_dir, "patch_0001.rp1")
    open(out, "wb").write(rp1)
    print("built %s (%d bytes, 1 entry)" % (out, len(rp1)))

    # 2) self-check with our own parser
    arch = Ra1Archive(out, expect_type=0x10)
    got = arch.read(arch.entry_by_name("Data/Script/localization.rsr"))
    assert got == test
    print("self-parse OK (type=%d, %d entries, roundtrip identical)" % (arch.type, arch.count))

    # 3) end-to-end: let the GAME load Data.ra1, then the patch, then read files
    print("emulating game loader ...")
    g = GameFileEmu()
    ok, cnt = g.load_archive("Data/Data.ra1", 1)
    print("  Data.ra1: open=%d, count=%d" % (ok, cnt))
    assert ok == 1
    ok, cnt = g.load_archive("Patch/patch_0001.rp1", 0x10)
    print("  patch_0001.rp1: open=%d, count=%d (logs hit: %d)" % (ok, cnt, len(g.logs)))
    assert ok == 1 and cnt == 2, "game rejected the patch!"

    data, size = g.load_file("Data/Script/localization.rsr")
    assert data is not None, "file not found via game loader"
    print("  read Data/Script/localization.rsr via game code: %d bytes" % size)
    assert data == test, "patched content mismatch!"
    print("  -> PATCHED content served (marker present: %s)" % (marker in data))

    # a file NOT in the patch must still come from Data.ra1 unchanged
    data2, size2 = g.load_file("Data/Script/init.rsd")
    e2 = base.entry_by_name("Data/Script/init.rsd")
    assert data2 == base.read(e2), "unpatched file changed!"
    print("  read Data/Script/init.rsd via game code: %d bytes (identical to original)" % size2)

    print("\nALL CHECKS PASSED: the rp1 patch channel works end-to-end with the game's own code.")
