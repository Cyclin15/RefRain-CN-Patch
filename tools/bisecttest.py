# -*- coding: utf-8 -*-
"""二分定位: 只翻译 [lo, hi) 行构建补丁, 运行游戏, 看是否崩溃"""
import sys, io, os, glob, importlib.util, subprocess, time
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from packrp1 import build_rp1

GAME = r"D:\Steam\steamapps\common\RefRain - prism memories -"

def load_mod(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m

def build_CN():
    CN = {}
    for p in sorted(glob.glob(os.path.join(HERE, "cn", "part*.py"))):
        for k, v in getattr(load_mod(p, "p"+os.path.basename(p)), "CN", {}).items():
            CN[k] = v
    MUSIC_BLOCKS = {}
    for p in sorted(glob.glob(os.path.join(HERE, "cn", "part*music*.py"))):
        for k, v in getattr(load_mod(p, "pm"+os.path.basename(p)), "MUSIC_BLOCKS", {}).items():
            MUSIC_BLOCKS[k] = v
    from smokebuild import SMOKE
    for k, v in SMOKE.items():
        CN.setdefault(k, v)
    CN[4] = "欢迎来到M.R.S."
    # 音乐室分配 (与 finalbuild 相同)
    raw = open(os.path.join(HERE, "localization.rsr"), "rb").read().decode("shift_jis")
    rows = [l.split("\t") for l in raw.split("\n") if l]
    def units(s): return sum(2 if ord(c) > 0x2E80 else 1 for c in s)
    def split_music_block(text, en_rows):
        total_en = sum(len(e) for e in en_rows)
        out, pos = [], 0
        n = len(text)
        for e in en_rows:
            if pos >= n: out.append(" "); continue
            share = max(1, round(n * len(e) / total_en))
            tgt = min(n, pos + share)
            PUNCT = "。，！？…～、；：）」』）)>》"
            lo_, hi_ = max(pos + 4, tgt - 12), min(n, tgt + 10)
            cut = tgt
            for j in range(tgt, hi_):
                if text[j] in PUNCT: cut = j + 1; break
            else:
                for j in range(tgt - 1, lo_ - 1, -1):
                    if text[j] in PUNCT: cut = j + 1; break
            seg = text[pos:cut]
            while units(seg) > 66 and len(seg) > 4: seg = seg[:-1]; cut -= 1
            out.append(seg); pos = cut
        if pos < n: out[-1] += text[pos:]
        return [x or ' ' for x in out]
    i = 793
    while i <= 948:
        if rows[i][2].strip() == "": i += 1; continue
        j = i
        while j <= 948 and rows[j][2].strip() != "": j += 1
        todo = [r for r in range(i, j) if r not in CN]
        if i in MUSIC_BLOCKS and todo:
            segs = split_music_block(MUSIC_BLOCKS[i], [rows[r][2] for r in todo])
            for r, s in zip(todo, segs): CN[r] = s
        i = j
    return CN

def build_patch(CN, lo, hi):
    raw_b = open(os.path.join(HERE, "localization.rsr"), "rb").read()
    lines_b = raw_b.split(b"\r\n")
    out_b = []
    for idx, ln in enumerate(lines_b):
        if not ln or not (lo <= idx < hi) or idx not in CN or CN[idx] is None:
            out_b.append(ln); continue
        p = ln.split(b"\t")
        if len(p) != 3:
            out_b.append(ln); continue
        lead = p[2][:len(p[2]) - len(p[2].lstrip(b" "))]
        g = CN[idx].encode("gbk")
        out_b.append(p[0] + b"\t" + p[1] + b"\t" + lead + g)
    rsr = b"\r\n".join(out_b)
    font = open(os.path.join(HERE, "cnfont.ttf"), "rb").read()
    rp1 = build_rp1({"Data/Script/localization.rsr": rsr, "Data/Font/umeplus-cl-gothic.ttf": font})
    open(os.path.join(GAME, "Patch", "patch_0001.rp1"), "wb").write(rp1)
    return len(rp1)

def run_game(timeout=10):
    p = subprocess.Popen([os.path.join(GAME, "RefRain.exe")], cwd=GAME)
    t0 = time.time()
    while time.time() - t0 < timeout:
        if p.poll() is not None:
            return p.returncode, time.time() - t0
        time.sleep(0.3)
    p.kill()
    return None, time.time() - t0   # None = 还活着 (没崩)

if __name__ == "__main__":
    lo, hi = int(sys.argv[1]), int(sys.argv[2])
    CN = build_CN()
    n = build_patch(CN, lo, hi)
    ret, dt = run_game()
    status = "CRASH" if ret is not None else "ALIVE"
    print(f"rows [{lo},{hi}) -> {status} (code={ret}, {dt:.1f}s, patch={n}B)")
