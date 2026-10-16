# -*- coding: utf-8 -*-
"""
Build the Chinese replacement font for RefRain -prism memories-.

Base: Noto Sans SC (SIL OFL 1.1, freely redistributable) subset
(GB2312 full + ASCII + kana + fullwidth/symbols), variable font
instanced to static wght=500, renamed to family "RebRank UmePlus".

Hard constraint from the game (RefRain.exe 0x453eac):
    wmemcpy_s(fontbuf + 0x49a02a, 17, L"RebRank UmePlus"(utf16le) + 1 wchar, 17)
  -> writes 34 bytes at file offset 0x49a02a.
  In the original umeplus-cl-gothic.ttf the pid=3 family name string
  (UTF-16BE) starts at 0x49a029; the UTF-16LE write at +1 byte yields
  UTF-16BE "RebRank UmePlus\0" + trailing U+8374 (garbage after NUL, ignored).
  We pre-place the exact post-write bytes so the copy is a no-op:
    0x49a029:        00
    0x49a02a..+34:   52 00 65 00 62 00 52 00 61 00 6e 00 6b 00 20 00
                     55 00 6d 00 65 00 50 00 6c 00 75 00 73 00 00 00 83 74
  Family name record points at 0x49a029, length 34.
"""
import io
import struct
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

NOTO = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"
OUT = "cnfont.ttf"
FAMILY = "RebRank UmePlus"
FAMILY_STR_OFF = 0x49A029          # absolute file offset of the pid3 family name
WGHT = 500                         # static weight to instance the VF to

# exact bytes the game's rename write produces (post-write state)
RENAME_BYTES = bytes.fromhex(
    "5200650062005200610 06e006b00200055006d00650050006c0075007300 0000 8374"
    .replace(" ", ""))
assert len(RENAME_BYTES) == 34, len(RENAME_BYTES)
FAMILY_BYTES = b"\x00" + RENAME_BYTES   # 35 bytes: 0x49a029 .. 0x49a04c


def gb2312_charset():
    """All GB2312 codepoints (zones A1-F7) as unicode chars."""
    chars = set()
    for hi in range(0xA1, 0xF8):
        for lo in range(0xA1, 0xFF):
            try:
                ch = bytes([hi, lo]).decode("gb2312")
                chars.add(ch)
            except UnicodeDecodeError:
                pass
    return chars


def extra_charset():
    c = set()
    c.update(chr(x) for x in range(0x20, 0x7F))            # ASCII
    c.update(chr(x) for x in range(0x3000, 0x3040))        # CJK punctuation 、。「」
    c.update(chr(x) for x in range(0x3040, 0x3100))        # kana
    c.update(chr(x) for x in range(0xFF00, 0xFF5F))        # fullwidth forms ！？～
    c.update(chr(x) for x in range(0xFF61, 0xFFA0))        # halfwidth kana
    c.update("·—–…‘’“”‘’〔〕《》〈〉『』")
    c.update(chr(x) for x in range(0x2460, 0x24EB))        # ①-⑳
    c.update("©°±×÷")
    return c


def build_subset_text():
    chars = gb2312_charset() | extra_charset()
    return "".join(sorted(chars))


def subset_font():
    from fontTools import subset
    from fontTools.ttLib import TTFont
    from fontTools.varLib import instancer
    opts = subset.Options()
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    opts.name_legacy = True
    opts.glyph_names = False
    opts.layout_features = []          # drop GSUB/GPOS entirely (saves MBs)
    opts.hinting = True
    opts.notdef_outline = True
    opts.recalc_bounds = False
    opts.recalc_timestamp = False
    opts.drop_tables += ["DSIG", "FFTM", "GDEF", "Merged", "Silf", "STAT"]
    font = subset.load_font(NOTO, opts)
    ss = subset.Subsetter(options=opts)
    ss.populate(text=build_subset_text())
    ss.subset(font)
    # VF -> static weight (GDI/GetGlyphOutlineA 不保证支持变量字体)
    if "fvar" in font:
        instancer.instantiateVariableFont(font, {"wght": WGHT}, inplace=True)
    buf = io.BytesIO()
    font.save(buf)
    return buf.getvalue()


def parse_sfnt(data):
    tag = data[:4]
    assert tag == b"\x00\x01\x00\x00" or tag == b"true", tag
    num = struct.unpack(">H", data[4:6])[0]
    tables = {}
    order = []
    for i in range(num):
        o = 12 + 16 * i
        tg = bytes(data[o:o + 4])
        chk, off, ln = struct.unpack(">III", data[o + 4:o + 16])
        tables[tg] = (chk, bytes(data[off:off + ln]))
        order.append(tg)
    return tables, order


def checksum(b):
    b = b + b"\x00" * (-len(b) % 4)
    s = 0
    for i in range(0, len(b), 4):
        s = (s + struct.unpack(">I", b[i:i + 4])[0]) & 0xFFFFFFFF
    return s


def make_name_table(records, family_off_abs, name_table_off):
    """records: list of (pid, eid, lid, nid, string).
    The pid3 family record's string is at family_off_abs (pre-placed bytes).
    Other strings packed after the fixed 35-byte family slot."""
    # storage layout: [35-byte family slot][other strings]
    storage = bytearray()
    storage += FAMILY_BYTES                     # slot 0, abs = family_off_abs
    entries = []   # (pid,eid,lid,nid, length, offset) -- spec order: length THEN offset
    for pid, eid, lid, nid, s in records:
        raw = s.encode("utf-16-be") if pid == 3 else s.encode("latin-1")
        if pid == 3 and nid in (1, 16) and s == FAMILY:
            entries.append((pid, eid, lid, nid, 34, 0))
            continue
        off = len(storage)
        storage += raw + b"\x00\x00"
        entries.append((pid, eid, lid, nid, len(raw), off))
    hdr = struct.pack(">HHH", 0, len(entries), 6 + 12 * len(entries))
    recs = b"".join(struct.pack(">HHHHHH", *e) for e in entries)
    table = hdr + recs + bytes(storage)
    return table


def assemble(subset_data):
    tables, order = parse_sfnt(subset_data)
    sub_tables = {k: v[1] for k, v in tables.items() if k != b"name"}
    sub_order = [t for t in order if t != b"name"]

    n = len(sub_tables) + 1
    dir_end = 12 + 16 * n

    # layout: other tables first (4-aligned), then gap, then name table
    # positioned so the family slot lands at FAMILY_STR_OFF.
    placements = []
    pos = dir_end
    for tg in sub_order:
        if tg not in sub_tables:
            continue
        pos = (pos + 3) & ~3
        placements.append((tg, pos, len(sub_tables[tg])))
        pos += len(sub_tables[tg])

    # records for the new name table
    records = [
        # windows, en-US
        (3, 1, 0x409, 0, "RebRank UmePlus - Noto Sans SC subset, SIL OFL 1.1"),
        (3, 1, 0x409, 1, FAMILY),
        (3, 1, 0x409, 2, "Regular"),
        (3, 1, 0x409, 3, "RebRank-UmePlus"),
        (3, 1, 0x409, 4, FAMILY),
        (3, 1, 0x409, 6, "RebRankUmePlus"),
        # windows, zh-CN
        (3, 1, 0x804, 1, FAMILY),
        (3, 1, 0x804, 2, "Regular"),
        (3, 1, 0x804, 4, FAMILY),
        (3, 1, 0x804, 6, "RebRankUmePlus"),
        # macintosh
        (1, 0, 0, 1, FAMILY),
        (1, 0, 0, 2, "Regular"),
        (1, 0, 0, 4, FAMILY),
        (1, 0, 0, 6, "RebRankUmePlus"),
    ]

    # We must know the name table layout to compute where to place it:
    # name_table_off + 6 + 12*count + storage[0:35 -> family slot at +0]
    # family string abs = name_table_off + 6 + 12*len(records) = FAMILY_STR_OFF
    name_header_and_records = 6 + 12 * len(records)
    name_table_off = FAMILY_STR_OFF - name_header_and_records
    end_of_tables = pos
    assert name_table_off >= end_of_tables, (
        "subset too big: tables end at %#x, name table needs %#x"
        % (end_of_tables, name_table_off))
    name_table = make_name_table(records, FAMILY_STR_OFF, name_table_off)
    assert len(name_table) == name_header_and_records + 35 + (len(name_table) - name_header_and_records - 35)

    # build directory in the order: sub tables then name
    allplacements = placements + [(b"name", name_table_off, len(name_table))]
    # sanity: name table region must not overlap others
    for tg, off, ln in placements:
        assert off + ln <= name_table_off, (tg, hex(off), hex(name_table_off))

    # directory must be sorted-ish? GDI doesn't care; keep subset order + name last.
    entries = []
    for tg, off, ln in allplacements:
        body = sub_tables[tg] if tg != b"name" else name_table
        if tg == b"head":
            # checksum with checkSumAdjustment zeroed; placeholder for now
            body_c = bytearray(body)
            body_c[8:12] = b"\x00\x00\x00\x00"
            chk = checksum(bytes(body_c))
        else:
            chk = checksum(body)
        entries.append((tg, chk, off, ln))

    total = max(off + ln for _, off, ln in allplacements)
    total = (total + 3) & ~3
    out = bytearray(total)
    # searchRange etc.
    import math
    sr = 16
    while sr * 2 <= 16 * len(entries):
        sr *= 2
    sfnt_hdr = struct.pack(">IHHHH", 0x00010000, len(entries),
                           sr, int(math.log2(sr // 16)) * 16, 16 * len(entries))
    out[0:12] = sfnt_hdr
    for i, (tg, chk, off, ln) in enumerate(entries):
        o = 12 + 16 * i
        out[o:o + 4] = tg
        struct.pack_into(">III", out, o + 4, chk, off, ln)
        body = sub_tables[tg] if tg != b"name" else name_table
        out[off:off + ln] = body

    # checkSumAdjustment
    whole = checksum(bytes(out))  # with adjustment currently zero (head copied zeroed? no!)
    # head body was copied as-is; its checkSumAdjustment field holds SimHei's value.
    # find head offset and zero it, then compute.
    for i, (tg, chk, off, ln) in enumerate(entries):
        if tg == b"head":
            struct.pack_into(">I", out, off + 8, 0)
    whole = checksum(bytes(out))
    adj = (0xB1B0AFBA - whole) & 0xFFFFFFFF
    for i, (tg, chk, off, ln) in enumerate(entries):
        if tg == b"head":
            struct.pack_into(">I", out, off + 8, adj)
    return bytes(out)


def verify(data):
    from fontTools.ttLib import TTFont
    f = TTFont(io.BytesIO(data))
    fam = f["name"].getDebugName(1)
    # family string carries 2 trailing bytes after the NUL (the game's
    # rename writes 17 wchars; GDI truncates at the NUL) -> prefix check
    assert fam is not None and fam.split("\x00")[0] == FAMILY, repr(fam)
    # family string at right offset?
    fam = [r for r in f["name"].names if r.nameID == 1 and r.platformID == 3]
    for r in fam:
        # fontTools doesn't expose abs offsets; check raw bytes instead
        pass
    assert data[0x49a029:0x49a04c] == FAMILY_BYTES, data[0x49a029:0x49a04c].hex()
    cmap = f.getBestCmap()
    test = "米莉雅蒂缪斯棱镜记忆中的感谢谢欢迎来到中央区域消除攻击结束得分难度回放教程消息日志档案音乐播放器注销退出保存数据版本一致不能播放连接开始执行削 prvPRV0123456789（）「」！？～…—·ＡＢＣ０１２①②③"
    missing = [c for c in set(test) if ord(c) not in cmap]
    print("coverage missing:", missing)
    print("numGlyphs:", f["maxp"].numGlyphs)
    print("size:", len(data))
    return not missing


if __name__ == "__main__":
    sub = subset_font()
    print("subset size:", len(sub))
    out = assemble(sub)
    open(OUT, "wb").write(out)
    ok = verify(out)
    print("VERIFY:", "OK" if ok else "MISSING GLYPHS")
