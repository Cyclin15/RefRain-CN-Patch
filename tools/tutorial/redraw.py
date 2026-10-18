# -*- coding: utf-8 -*-
# 重绘 tutorial_obj_eng.png: 擦除英文、原位渲染中文
import sys, json
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from translation import T, KEEP

FONT = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"
SS = 4  # 超采样倍数

WHITE = (250, 250, 250)
YELLOW = (248, 200, 0)
GRAY = (152, 152, 152)

import os
HERE = os.path.dirname(os.path.abspath(__file__))
GAME = r"D:\Steam\steamapps\common\RefRain - prism memories -"

sprites = json.load(open(os.path.join(HERE, "sprites.json")))
emap = {s["id"]: s for s in sprites if s["tex"] == 10141}

# 源图: 优先用工作区已提取的, 否则从游戏 Data.ra1 提取
src_png = os.path.join(HERE, "tutorial_obj_eng.png")
if not os.path.exists(src_png):
    sys.path.insert(0, os.path.dirname(HERE))
    from raf1 import Ra1Archive
    a = Ra1Archive(os.path.join(GAME, "Data", "Data.ra1"), expect_type=1)
    open(src_png, "wb").write(a.read(a.entry_by_name("data/grp/tutorial_obj_eng.png")))
    print("已从 Data.ra1 提取原图 ->", src_png)
atlas = Image.open(src_png).convert("RGBA")

# ---- 精灵矩形无重叠校验 ----
rects = [(s["u"], s["v"], s["w"], s["h"]) for s in emap.values()]
for i in range(len(rects)):
    for j in range(i + 1, len(rects)):
        u1, v1, w1, h1 = rects[i]; u2, v2, w2, h2 = rects[j]
        if u1 < u2 + w2 and u2 < u1 + w1 and v1 < v2 + h2 and v2 < v1 + h1:
            print("OVERLAP!", rects[i], rects[j])

A = np.array(atlas)

def parse_segments(text):
    segs, cur, kw = [], "", False
    for c in text:
        if c == "【":
            if cur: segs.append((cur, kw)); cur = ""
            kw = True
        elif c == "】":
            if cur: segs.append((cur, kw)); cur = ""
            kw = False
        else:
            cur += c
    if cur: segs.append((cur, kw))
    return segs

def build_strip(text, size, weight, body_color, kw_color):
    f = ImageFont.truetype(FONT, size * SS)
    f.set_variation_by_axes([weight])
    imgs = []
    for t, k in parse_segments(text):
        w = int(f.getlength(t)) + 8
        h = size * SS + size * SS // 2
        im = Image.new("L", (w, h), 0)
        ImageDraw.Draw(im).text((4, size * SS // 6), t, font=f, fill=255)
        im = im.resize((max(w // SS, 1), max(h // SS, 1)), Image.LANCZOS)
        col = kw_color if k else body_color
        rgba = Image.new("RGBA", im.size, col + (0,))
        rgba.putalpha(im)
        imgs.append(rgba)
    W = sum(i.width for i in imgs)
    H = max(i.height for i in imgs)
    out = Image.new("RGBA", (max(W, 1), H), (0, 0, 0, 0))
    x = 0
    for im in imgs:
        out.paste(im, (x, 0), im)
        x += im.width
    return out

def gold_gradient(strip):
    """把白色文字条重新着色为金色垂直渐变 (255,240,178)->(255,208,18)"""
    px = np.array(strip).astype(np.int16)
    alpha = px[..., 3]
    rows = np.where((alpha > 40).any(axis=1))[0]
    if len(rows) < 2:
        return strip
    y0, y1 = rows[0], rows[-1]
    for y in range(y0, y1 + 1):
        t = (y - y0) / max(y1 - y0, 1)
        px[y, :, 0] = 255
        px[y, :, 1] = round(240 - 32 * t)
        px[y, :, 2] = round(178 - 160 * t)
    return Image.fromarray(px.astype(np.uint8))

STYLE = {  # style -> (base_size, weight, 颜色或None=渐变, 左对齐?)
    "dialog":       (13, 500, ("white",), True),
    "dialog_yellow":(13, 500, ("yellow_dim",), True),
    "menu_white":   (13, 500, ("white",), True),
    "menu_dim":     (13, 500, ("gray",), True),
    "menu_active":  (13, 500, ("yellow",), True),
    "objective":    (13, 500, ("white",), False),
    "label":        (15, 700, ("white",), False),
    "header":       (15, 700, ("gold",), False),
    "label_gold":   (15, 700, ("gold",), False),
}

def color_pair(kind):
    if kind == "white": return WHITE, YELLOW  # 对话: 白色正文 + 黄色关键词
    if kind == "yellow": return YELLOW, YELLOW
    if kind == "yellow_dim":
        yd = (248, 200, 0)
        return yd, yd
    if kind == "gray": return GRAY, GRAY
    return WHITE, YELLOW  # gold: 占位, 之后渐变

def ink_bbox(sid):
    """原精灵文字墨迹范围 (在将擦除的区域内统计)"""
    s = emap[sid]
    style = T[sid][0]
    x0, x1 = 0, s["w"]
    y0, y1 = 0, s["h"]
    if style in ("header", "label_gold"):
        y1 = min(13, s["h"])  # 跳过 y13-14 下划线
    if sid == 10266:
        x0, x1 = 22, 162      # 跳过波纹装饰
    reg = A[s["v"] + y0:s["v"] + y1, s["u"] + x0:s["u"] + x1, 3]
    ys, xs = np.where(reg > 40)
    if len(xs) == 0:
        return None
    return (x0 + int(xs.min()), x0 + int(xs.max()),
            y0 + int(ys.min()), y0 + int(ys.max()))

changed = []
for sid, (style, text) in sorted(T.items()):
    s = emap[sid]
    u, v, w, h = s["u"], s["v"], s["w"], s["h"]
    bb = ink_bbox(sid)

    # ---- 擦除 (RGB 一起清零, 避免半透明边缘混入旧色) ----
    if style in ("header", "label_gold"):
        ey = min(13, h)  # 保留 y>=13 的下划线
        ex0, ex1 = (22, 162) if sid == 10266 else (0, w)
        A[v:v + ey, u + ex0:u + ex1, :3] = 0
        A[v:v + ey, u + ex0:u + ex1, 3] = 0
    else:
        A[v:v + h, u:u + w, :3] = 0
        A[v:v + h, u:u + w, 3] = 0

    # ---- 渲染 ----
    base, weight, (kind,), left_align = STYLE[style]
    if kind == "gold":
        body = kw = WHITE  # 占位, 渐变在 gold_gradient 处理
    else:
        body, kw = color_pair(kind)

    # 可用区域: 对话/菜单垂直限制在 y2..h-2 (原文 y4-14, 避免贴边)
    if style in ("header", "label_gold"):
        band_t, band_b = 1, min(13, h) - 1
        max_w = (162 - 22) if sid == 10266 else w - 4
    else:
        band_t, band_b = 2, h - 2
        max_w = w - 4

    strip = None
    for size in range(base, 6, -1):
        st = build_strip(text, size, weight, body, kw)
        bbx = st.split()[3].getbbox()
        if bbx is None:
            strip = st
            break
        ink_w = bbx[2] - bbx[0]
        ink_h = bbx[3] - bbx[1]
        if ink_w <= max_w and ink_h <= (band_b - band_t + 1):
            strip = st
            break
    if strip is None:
        print(f"!! {sid} 无法适配: {text}")
        continue
    if kind == "gold":
        strip = gold_gradient(strip)
    bbx = strip.split()[3].getbbox() or (0, 0, strip.width, strip.height)
    ink_w, ink_h = bbx[2] - bbx[0], bbx[3] - bbx[1]

    # 垂直: 墨迹在 band 内居中
    ty = band_t + (band_b - band_t + 1 - ink_h) // 2 - bbx[1]
    # 水平: 墨迹左缘 (左对齐) 或墨迹中心 (居中)
    if sid == 10266:
        tx_ink = (22 + 161) // 2 - ink_w // 2
    elif left_align:
        tx_ink = (bb[0] if bb else 2)
    else:
        cx = (bb[0] + bb[1]) // 2 if bb else w // 2
        tx_ink = cx - ink_w // 2
    if tx_ink < 1: tx_ink = 1
    if tx_ink + ink_w > w - 1: tx_ink = w - 1 - ink_w
    tx = tx_ink - bbx[0]

    # numpy 直接合成 (paste 用 alpha 做 mask 会把 alpha 平方)
    sx, sy = u + tx, v + ty
    sx0, sy0 = max(sx, 0), max(sy, 0)
    sx1, sy1 = min(sx + strip.width, A.shape[1]), min(sy + strip.height, A.shape[0])
    if sx1 > sx0 and sy1 > sy0:
        sub = np.array(strip)[sy0 - sy:sy1 - sy, sx0 - sx:sx1 - sx]
        m = sub[..., 3] > 0
        A[sy0:sy1, sx0:sx1][m] = sub[m]
    changed.append((sid, size, text))

# ---- 写回 ----
out = Image.fromarray(A)
out.save(os.path.join(HERE, "tutorial_obj_chn.png"))
print(f"重绘 {len(changed)} 个精灵 -> tutorial_obj_chn.png")

# ---- 检查遗漏: tex=10141 中既不在 T 也不在 KEEP、但有墨迹的精灵 ----
for s in emap.values():
    sid = s["id"]
    if sid in T or sid in KEEP:
        continue
    reg = A[s["v"]:s["v"] + s["h"], s["u"]:s["u"] + s["w"], 3]
    if (reg > 40).any():
        n = int((reg > 40).sum())
        print(f"?? 未处理精灵 {sid} ({s['w']}x{s['h']}) 有墨迹 {n}px")

# ---- 越界检查 (header 跳过 y>=13 的下划线行) ----
print("\n== 越界检查 ==")
bad = 0
sizes = {}
for sid, size, text in changed:
    sizes[size] = sizes.get(size, 0) + 1
print("字号分布:", dict(sorted(sizes.items(), reverse=True)))
for sid, (style, text) in T.items():
    s = emap[sid]
    yhi = min(13, s["h"]) if style in ("header", "label_gold") else s["h"]
    reg = A[s["v"]:s["v"] + yhi, s["u"]:s["u"] + s["w"], 3]
    ys, xs = np.where(reg > 40)
    if len(xs) and (xs.min() < 1 or xs.max() > s["w"] - 2 or ys.min() < 1 or ys.max() > yhi - 2):
        print(f"  !! {sid} 贴边: x[{xs.min()},{xs.max()}] y[{ys.min()},{ys.max()}] w={s['w']} yhi={yhi}")
        bad += 1
print(f"  贴边精灵数: {bad}")

# ---- 预览图: 3x 放大, 每行一个精灵 ----
from PIL import ImageDraw as ID2
sc = 3
pad = 6
lines = []
for sid, size, text in changed:
    s = emap[sid]
    crop = out.crop((s["u"], s["v"], s["u"] + s["w"], s["v"] + s["h"]))
    crop = crop.resize((s["w"] * sc, s["h"] * sc), Image.NEAREST)
    lines.append((sid, text, crop))
cols = 3
rows = (len(lines) + cols - 1) // cols
cw = max(l[2].width for l in lines) + pad
chh = max(l[2].height for l in lines) + pad + 10
pv = Image.new("RGBA", (cols * cw, rows * chh), (20, 20, 30, 255))
d = ID2.Draw(pv)
for i, (sid, text, crop) in enumerate(lines):
    x = (i % cols) * cw; y = (i // cols) * chh
    pv.paste(crop, (x + pad, y + 10), crop)
    d.text((x + pad, y + 1), str(sid), fill=(150, 150, 150, 255))
pv.save(os.path.join(HERE, "preview_chn.png"))
print("预览 -> preview_chn.png")
