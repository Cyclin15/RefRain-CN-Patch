# -*- coding: utf-8 -*-
"""Smoke test: build a small Chinese patch (title + menus + font) and install it."""
import sys, io, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from packrp1 import build_rp1

GAME = r"D:\Steam\steamapps\common\RefRain - prism memories -"

# --- smoke translations: row index (0-based, matches localization.rsr line) -> Chinese
SMOKE = {
    0: "RefRain -棱镜记忆- (Web体验版)",
    1: "RefRain -棱镜记忆-",
    2: "欢迎来到M.R.S.",
    3: "收到新消息！",
    5: "收到新消息！",
    6: "发现了新的接入点。",
    7: "RefRain -棱镜记忆- / 第1话",
    66: "有新消息。",
    68: "有新消息。",
    81: "退出程序",
    96: "以Easy难度开始游戏",
    97: "以Normal难度开始游戏",
    98: "以Advanced难度开始游戏",
    99: "以Extreme难度开始游戏",
    752: "无法观看这个回放",
    753: "版本不一致，无法播放",
    754: "开始连接M.R.S. 中央1",
    755: "开始连接M.R.S. 中央1",
    756: "执行教学程序",
    757: "开始连接M.R.S.",
    758: "打开消息日志档案（Web体验版中无法使用）",
    759: "启动音乐播放器（Web体验版中无法使用）",
    760: "播放回放（Web体验版中无法使用）",
    761: "注销并断开连接",
    762: "开始连接M.R.S.",
    763: "打开消息日志档案",
    764: "启动音乐播放器",
    765: "播放回放",
    766: "注销并断开连接",
    767: "开始连接M.R.S. 中央1",
    768: "开始连接M.R.S. 中央1",
    769: "执行教学程序",
    770: "开始连接M.R.S.",
    771: "打开消息日志档案（Web体验版中无法使用）",
    772: "启动音乐播放器（Web体验版中无法使用）",
    773: "播放回放（Web体验版中无法使用）",
    774: "注销并断开连接",
    775: "开始连接M.R.S.",
    776: "打开消息日志档案",
    777: "启动音乐播放器",
    778: "播放回放",
    779: "注销并断开连接",
    780: "开始连接M.R.S. 中央1",
    781: "开始连接M.R.S. 中央1",
    782: "执行教学程序",
    783: "连接M.R.S.哦",
    784: "看消息哦（Web体验版中用不了哦）",
    785: "听音乐哦（Web体验版中用不了哦）",
    786: "看回放哦（Web体验版中用不了哦）",
    787: "拜拜～",
    788: "连接M.R.S.哦",
    789: "看消息哦（Web体验版中用不了哦）",
    790: "听音乐哦（Web体验版中用不了哦）",
    791: "看回放哦（Web体验版中用不了哦）",
    792: "拜拜～",
    # --- prologue archive (rows 138-177) ---
    138: "我的名字？",
    139: "我、我是……好像叫米莉雅。",
    140: "问我的名字……那你又是谁？",
    141: "是谁……在叫我吗？",
    142: "必须去中央5才行……",
    143: "来自赛蕾丝的消息：",
    144: "米莉雅，你又来到中央1了呢。",
    145: "米莉雅：",
    146: "？",
    147: "赛蕾丝：",
    148: "果然……你好像什么都不记得了。",
    149: "米莉雅：",
    150: "……？",
    151: "赛蕾丝：",
    152: "连这个档案库的用途都忘了吗？",
    153: "米莉雅：",
    154: "你……知道关于我的什么事吗？",
    155: "赛蕾丝：",
    156: "……我现在可不打算回答这个问题。",
    157: "目标锁定。开始排除行动。",
    158: "来自蒂的消息：",
    159: "简直难以置信！",
    160: "米莉雅这家伙，连人家的内存区域都给用掉了。",
    161: "害人家都没法在M.R.S.里玩了，真是的！！",
    162: "看样子你把我忘得一干二净了……太过分了啦。",
    163: "「人家是蒂呀」，这话都说第几遍了！？",
    164: "……咦，是第几遍了来着？",
    165: "算了，无所谓啦。",
    166: "米莉雅：",
    167: "对不起，那个……请问，您是哪位？",
    168: "蒂：",
    169: "啊——好好好，反正也不是一回两回了。",
    170: "是蒂呀，蒂。人家是蒂！",
    171: "不过这下麻烦了。",
    172: "米莉雅和人家没法同时行动了。",
    173: "我猜是M.R.S.的资源不太够用了。",
    174: "蒂：",
    175: "总之，以后记得切换着用哦。",
    176: "光可着你米莉雅一个人用，可是要挨骂的哦。",
    177: "啊，切换是从菜单的登录那进行的哦。",
}


def build_rsr():
    raw = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "localization.rsr"), "rb").read()
    lines = raw.split(b"\r\n")
    out = []
    for i, ln in enumerate(lines):
        if not ln:
            out.append(ln)
            continue
        p = ln.split(b"\t")
        if i in SMOKE and len(p) == 3:
            en = p[2]
            lead = en[:len(en) - len(en.lstrip(b" "))]
            cn = SMOKE[i].encode("gbk")
            assert b"\t" not in cn and b"\r" not in cn and b"\n" not in cn
            out.append(p[0] + b"\t" + p[1] + b"\t" + lead + cn)
        else:
            out.append(ln)
    return b"\r\n".join(out)


def main():
    rsr = build_rsr()
    # sanity: every smoke line round-trips
    for i, ln in enumerate(rsr.split(b"\r\n")):
        if i in SMOKE:
            assert SMOKE[i] in ln.decode("gbk", "replace"), i
    # every Chinese char must exist in the replacement font
    from fontTools.ttLib import TTFont
    cmap = TTFont("cnfont.ttf").getBestCmap()
    for i, s in SMOKE.items():
        for ch in s:
            if ord(ch) > 127 and ord(ch) not in cmap:
                raise SystemExit(f"missing glyph U+{ord(ch):04X} {ch!r} (row {i})")
    print("cmap coverage OK")
    font = open("cnfont.ttf", "rb").read()
    files = {
        "Data/Script/localization.rsr": rsr,
        "Data/Font/umeplus-cl-gothic.ttf": font,
    }
    rp1 = build_rp1(files)
    outdir = os.path.join(GAME, "Patch")
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "patch_0001.rp1")
    open(out, "wb").write(rp1)
    print("wrote", out, len(rp1), "bytes")

    # verify with our own parser
    from raf1 import Ra1Archive
    a = Ra1Archive(out, expect_type=0x10)
    e = a.entry_by_name("data/script/localization.rsr")
    got = a.read(e)
    assert got == rsr, "localization.rsr mismatch"
    e2 = a.entry_by_name("data/font/umeplus-cl-gothic.ttf")
    got2 = a.read(e2)
    assert got2 == font, "font mismatch"
    print("self-parse OK: patched files served correctly")


if __name__ == "__main__":
    main()
