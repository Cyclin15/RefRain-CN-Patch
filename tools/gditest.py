# -*- coding: utf-8 -*-
"""GDI pre-validation: emulate the game's exact font path with cnfont.ttf."""
import ctypes
import ctypes.wintypes as wt
import struct
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

gdi32 = ctypes.windll.gdi32
user32 = ctypes.windll.user32

FR_PRIVATE = 0x10
GB2312_CHARSET = 134
GGO_GRAY8_BITMAP = 6
LF_FACESIZE = 32

data = bytearray(open("cnfont.ttf", "rb").read())
print("font size:", hex(len(data)))

# --- simulate the game's rename write: wmemcpy_s(buf+0x49a02a, 17, L"RebRank UmePlus..", 17)
src = ctypes.create_string_buffer(34)
raw = ("RebRank UmePlus\x00").encode("utf-16-le") + b"\x83\x74"  # 17th wchar = 0x7483
src.raw = raw
ctypes.CDLL("msvcrt").wmemcpy_s(ctypes.c_void_p(id(data) + 0), 0, None, 0) if False else None
# do it in python (same effect)
data[0x49A02A:0x49A02A + 34] = raw
print("rename write applied; family slot now:", bytes(data[0x49A029:0x49A029+20]).hex(" "))

# --- register
cnt = ctypes.c_uint()
fbuf = (ctypes.c_char * len(data)).from_buffer(data)
hFontMem = gdi32.AddFontMemResourceEx(fbuf, len(data), 0, ctypes.byref(cnt))
print("AddFontMemResourceEx:", hex(hFontMem or 0), "fonts:", cnt.value)
assert hFontMem

# --- LOGFONT: GB2312 charset, face RebRank UmePlus, height 12, weight 500
class LOGFONT(ctypes.Structure):
    _fields_ = [("lfHeight", ctypes.c_long), ("lfWidth", ctypes.c_long),
                ("lfEscapement", ctypes.c_long), ("lfOrientation", ctypes.c_long),
                ("lfWeight", ctypes.c_long), ("lfItalic", ctypes.c_byte),
                ("lfUnderline", ctypes.c_byte), ("lfStrikeOut", ctypes.c_byte),
                ("lfCharSet", ctypes.c_byte), ("lfOutPrecision", ctypes.c_byte),
                ("lfClipPrecision", ctypes.c_byte), ("lfQuality", ctypes.c_byte),
                ("lfPitchAndFamily", ctypes.c_byte), ("lfFaceName", ctypes.c_char * LF_FACESIZE)]

lf = LOGFONT(24, 0, 0, 0, 500, 0, 0, 0, GB2312_CHARSET, 0, 0, 2, 0x31)
lf.lfFaceName = b"RebRank UmePlus"
hfont = gdi32.CreateFontIndirectA(ctypes.byref(lf))
print("HFONT:", hex(hfont or 0))
assert hfont

# --- DC
hdc = user32.GetDC(0)
old = gdi32.SelectObject(hdc, hfont)

class MAT2(ctypes.Structure):
    _fields_ = [("eM11", ctypes.c_uint32), ("eM12", ctypes.c_uint32),
                ("eM21", ctypes.c_uint32), ("eM22", ctypes.c_uint32)]
mat = MAT2()
mat.eM11 = 0x00010000; mat.eM22 = 0x00010000   # FIXED 16.16 identity

class GLYPHMETRICS(ctypes.Structure):
    _fields_ = [("gmBlackBoxX", wt.UINT), ("gmBlackBoxY", wt.UINT),
                ("gmptGlyphOrigin", wt.POINT), ("gmCellIncX", ctypes.c_short),
                ("gmCellIncY", ctypes.c_short)]

def render(text):
    """Render text (str) via GetGlyphOutlineA with GBK uChars; returns list of (bitmap, gm)."""
    glyphs = []
    for ch in text:
        if ord(ch) < 0x80:
            u = ord(ch)
        else:
            b = ch.encode("gbk")
            u = (b[0] << 8) | b[1]
        gm = GLYPHMETRICS()
        need = gdi32.GetGlyphOutlineA(hdc, u, GGO_GRAY8_BITMAP, ctypes.byref(gm), 0, None, ctypes.byref(mat))
        if need in (0xFFFFFFFF, 0) or gm.gmBlackBoxX == 0:
            glyphs.append(None)
            print(f"  char {ch!r} (u={u:#06x}): NO GLYPH (need={need})")
            continue
        buf = ctypes.create_string_buffer(need)
        r = gdi32.GetGlyphOutlineA(hdc, u, GGO_GRAY8_BITMAP, ctypes.byref(gm), need, buf, ctypes.byref(mat))
        glyphs.append((buf.raw[:need], gm))
    return glyphs

TEST = "米莉雅：欢迎来到M.R.S.！棱镜记忆～ 未知字：挧"
glyphs = render(TEST)

# compose into a PNG (grayscale)
from PIL import Image
gm0 = [g for g in glyphs if g]
if not gm0:
    print("NO GLYPHS RENDERED"); sys.exit(1)
asc = max(g.gmptGlyphOrigin.y for _, g in gm0)
desc = max(g.gmBlackBoxY - g.gmptGlyphOrigin.y for _, g in gm0)
H = asc + desc + 4
W = 8
for g in glyphs:
    W += (g[1].gmCellIncX if g else 10) + 2
img = Image.new("L", (W + 20, H), 0)
px = img.load()
x = 10
for g in glyphs:
    if not g:
        x += 12
        continue
    raw, gm = g
    gw, gh = gm.gmBlackBoxX, gm.gmBlackBoxY
    stride = (gw * 4 + 3) & ~3  # GGO_GRAY8: 4 bits per pixel? NO: 8bpp, aligned to 4
    stride = (gw + 3) & ~3
    y0 = asc - gm.gmptGlyphOrigin.y
    for row in range(gh):
        line = raw[row*stride: row*stride + gw]
        for col in range(gw):
            v = line[col]  # 0..64 alpha in GGO_GRAY8
            px[x + col, y0 + row] = min(255, v * 4)
    x += gm.gmCellIncX + 2
img.save("gditest.png")
print("saved gditest.png", img.size)
user32.ReleaseDC(0, hdc)
