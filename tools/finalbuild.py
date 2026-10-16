# -*- coding: utf-8 -*-
"""最终构建: 合并全部翻译 -> localization.rsr(GBK) + cnfont.ttf -> patch_0001.rp1"""
import sys, io, os, glob, importlib.util
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from packrp1 import build_rp1

GAME = r"D:\Steam\steamapps\common\RefRain - prism memories -"
MUSIC_START, MUSIC_END = 793, 948   # 音乐室解说区域
WIDTH_CAP = 66                       # 每行显示宽度上限 (半角=1, 全角=2)

def load_mod(path):
    spec = importlib.util.spec_from_file_location(os.path.basename(path)[:-3], path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

# ---------- 收集翻译 ----------
CN = {}
for p in sorted(glob.glob(os.path.join(HERE, "cn", "part*.py"))):
    m = load_mod(p)
    cn = getattr(m, "CN", {})
    for k, v in cn.items():
        CN[k] = v
MUSIC_BLOCKS = {}
for p in sorted(glob.glob(os.path.join(HERE, "cn", "part*music*.py"))):
    m = load_mod(p)
    for k, v in getattr(m, "MUSIC_BLOCKS", {}).items():
        MUSIC_BLOCKS[k] = v

from smokebuild import SMOKE
# smokebuild 导入时重包了 stdout (旧包装器被 GC 时会关闭底层缓冲), 重新包装
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for k, v in SMOKE.items():
    CN.setdefault(k, v)
CN[4] = "欢迎来到M.R.S."   # 冒烟集遗漏的重复行

# ---------- 读原文 ----------
raw = open(os.path.join(HERE, "localization.rsr"), "rb").read().decode("shift_jis")
lines = raw.split("\n")
assert len(lines) == 950, len(lines)  # 949 行 + 末尾空
rows = [l.split("\t") for l in lines if l]
assert len(rows) == 949

def units(s):
    return sum(2 if ord(c) > 0xFF00 or ord(c) > 0x2E80 else 1 for c in s)

def split_music_block(text, en_rows):
    """把整段中文按各行 EN 长度比例分配, 优先在标点后断行, 宽度不超限."""
    total_en = sum(len(e) for e in en_rows)
    out, pos = [], 0
    n = len(text)
    for e in en_rows:
        if pos >= n:
            out.append(" ")
            continue
        share = max(1, round(n * len(e) / total_en))
        tgt = min(n, pos + share)
        # 在目标附近向后找标点 (最多+10), 向前找标点 (最多-12)
        PUNCT = "。，！？…～、；：）」』）)>》"
        lo, hi = max(pos + 4, tgt - 12), min(n, tgt + 10)
        cut = tgt
        for j in range(tgt, hi):
            if text[j] in PUNCT:
                cut = j + 1
                break
        else:
            for j in range(tgt - 1, lo - 1, -1):
                if text[j] in PUNCT:
                    cut = j + 1
                    break
        seg = text[pos:cut]
        # 宽度超限时向前硬切
        while units(seg) > WIDTH_CAP and len(seg) > 4:
            seg = seg[:-1]
            cut -= 1
        out.append(seg)
        pos = cut
    if pos < n:  # 有剩余, 追加到最后一行
        out[-1] += text[pos:]
    return [x or ' ' for x in out]

# 音乐室整块分配
music_cn = {}
i = MUSIC_START
while i <= MUSIC_END:
    en = rows[i][2]
    if en.strip() == "":
        i += 1
        continue
    j = i
    while j <= MUSIC_END and rows[j][2].strip() != "":
        j += 1
    block = list(range(i, j))
    todo = [r for r in block if r not in CN]
    if i in MUSIC_BLOCKS and todo:
        segs = split_music_block(MUSIC_BLOCKS[i], [rows[r][2] for r in todo])
        assert len(segs) == len(todo), (i, len(segs), len(todo))
        for r, s in zip(todo, segs):
            music_cn[r] = s
    i = j
for k, v in music_cn.items():
    CN[k] = v

# ---------- 生成 rsr ----------
out_lines = []
translated = 0
for idx, ln in enumerate(lines):
    if not ln:
        out_lines.append(ln)
        continue
    p = ln.split("\t")
    if idx in CN and CN[idx] is not None and len(p) == 3:
        en = p[2]
        lead = en[:len(en) - len(en.lstrip(" "))]
        cn = CN[idx]
        g = cn.encode("gbk")
        assert b"\t" not in g and b"\r" not in g and b"\n" not in g, idx
        out_lines.append(p[0] + "\t" + p[1] + "\t" + lead + cn)
        translated += 1
    else:
        out_lines.append(ln)
rsr = "\n".join(out_lines).encode("shift_jis", errors="replace")
# rsr 必须整体用 SJIS 编码吗? 不: 文本列是 GBK, 只有行结构是 ASCII.
# 重新用纯字节方式构建: 结构字节都是 ASCII, GBK 字节直接嵌入.
raw_b = open(os.path.join(HERE, "localization.rsr"), "rb").read()
lines_b = raw_b.split(b"\r\n")
assert len(lines_b) == len(lines), (len(lines_b), len(lines))
out_b = []
for idx, ln in enumerate(lines_b):
    if not ln:
        out_b.append(ln)
        continue
    p = ln.split(b"\t")
    if idx in CN and CN[idx] is not None and len(p) == 3:
        en = p[2]
        lead = en[:len(en) - len(en.lstrip(b" "))]
        g = CN[idx].encode("gbk")
        assert b"\t" not in g and b"\r" not in g and b"\n" not in g, idx
        out_b.append(p[0] + b"\t" + p[1] + b"\t" + lead + g)
    else:
        out_b.append(ln)
rsr = b"\r\n".join(out_b)

# ---------- 校验 ----------
# 1) 回读: 每行 3 列, MSG 序号完整, 已译行 GBK 可解码
chk = rsr.split(b"\r\n")
assert len(chk) == 950
n_ok = 0
for idx, ln in enumerate(chk):
    if not ln:
        continue
    p = ln.split(b"\t")
    assert len(p) == 3, (idx, p)
    assert p[0] == rows[idx][0].encode(), idx
    if idx in CN and CN[idx] is not None:
        s = (p[2].decode("gbk"))
        assert CN[idx] in s or CN[idx].strip() == "", idx
        n_ok += 1
print(f"translated rows: {n_ok} / 949")

# 2) 全部中文/全角字符必须在字体 cmap 中
from fontTools.ttLib import TTFont
cmap = TTFont(os.path.join(HERE, "cnfont.ttf")).getBestCmap()
missing = []
for idx, s in CN.items():
    if s is None:
        continue
    for ch in s:
        if ord(ch) > 127 and ord(ch) not in cmap:
            missing.append((idx, ch, hex(ord(ch))))
if missing:
    for m_ in missing[:20]:
        print("MISSING GLYPH:", m_)
    raise SystemExit("missing glyphs")
print("cmap coverage OK")

# 3) 行76 占位符数量一致
n_ps_en = rows[76][2].count("%s")
n_ps_cn = CN[76].count("%s")
assert n_ps_en == n_ps_cn, (n_ps_en, n_ps_cn)
print("row76 placeholders OK:", n_ps_cn)

# 4) 音乐室行宽
for idx in range(MUSIC_START, MUSIC_END + 1):
    p = chk[idx].split(b"\t")
    s = p[2].decode("gbk")
    u = units(s)
    assert u <= 70, (idx, u, s)
print("music room line widths OK")

# 5) 保留行检查: 291 故意乱码, 原样保留
assert chk[291].split(b"\t")[2] == lines_b[291].split(b"\t")[2]
print("special rows OK")

# ---------- 打包 ----------
font = open(os.path.join(HERE, "cnfont.ttf"), "rb").read()
rp1 = build_rp1({
    "Data/Script/localization.rsr": rsr,
    "Data/Font/umeplus-cl-gothic.ttf": font,
})
outdir = os.path.join(GAME, "Patch")
os.makedirs(outdir, exist_ok=True)
out = os.path.join(outdir, "patch_0001.rp1")
open(out, "wb").write(rp1)
print("wrote", out, len(rp1), "bytes")

from raf1 import Ra1Archive
a = Ra1Archive(out, expect_type=0x10)
e = a.entry_by_name("data/script/localization.rsr")
assert a.read(e) == rsr
e2 = a.entry_by_name("data/font/umeplus-cl-gothic.ttf")
assert a.read(e2) == font
print("self-parse OK")
print("DONE")
