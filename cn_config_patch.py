# -*- coding: utf-8 -*-
"""RefRain - prism memories - config.exe 简体中文化补丁（发布版，需 Python 3）

用法：把本文件放到游戏根目录（config.exe 所在目录），运行：
    python cn_config_patch.py

原理：解析 config.exe 内嵌的 .NET .resources 资源块，把 UI 字符串替换为中文，
数据在原位重打包，文件总大小不变，不改动任何程序逻辑。
原始文件会备份为 config.exe.bak。
"""
import sys, os, hashlib, struct, shutil

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

ORIG_SHA256  = "eb55fa47960dc91b558a60536777a071ccc78cf2e44a42f1c7eee48bd9c0b376"
PATCHED_SHA256 = "f7c2d92ed8a47ba2cbcd7651bf36dc1c124f40a86501bae633634d7aa20f6ffa"
FILESIZE = 264192

# 4 个资源块在 config.exe 内的 (偏移, 大小) 与对应翻译表标签
BLOBS = [
    (0x5eb0,  1303,   "PROPS"),     # Config.Properties.Resources.resources (ja)
    (0x63cb,  100092, "FRM"),       # RefRainConfig.FrmMain.resources (ja)
    (0x29631, 48399,  "FRM_EN"),    # RefRainConfig.FrmMain.en.resources
    (0x35344, 1130,   "PROPS_EN"),  # Config.Properties.Resources.en.resources
]

# ---------------- 翻译表 ----------------
FRM = {
    "$this.Text": "RefRain 设置工具",
    "AdvanceGroup.Text": "高级设置",
    "BasicGroup.Text": "基本设置",
    "BtnClose.Text": "关闭",
    "BtnDefault.Text": "恢复默认",
    "BtnTwitter.Text": "Twitter设置",
    "BtnWrite.Text": "保存设置",
    "BtnWriteRun.Text": "保存并启动",
    "ChkAspectBorder.Text": "宽屏全屏时左右显示黑边",
    "ChkAutoShift.Text": "按住射击键时低速移动",
    "ChkAutoUpdate.Text": "启动游戏时检查更新",
    "ChkEnableFog.Text": "启用雾效果",
    "ChkMusic.Text": "播放BGM",
    "ChkShowAllMusic.Text": "音乐室中显示未播放过的曲目",
    "ChkShowHitRect.Text": "显示自机判定点",
    "ChkSound.Text": "播放音效",
    "ChkTwitter.Text": "通关后发推文",
    "ChkTwitterHighscore.Text": "仅刷新最高分时发推",
    "ChkUpdateConfirm.Text": "更新前显示确认对话框",
    "ChkWindow.Text": "以窗口模式启动",
    "ChkWindowBorder.Text": "显示窗口边框",
    "CmbFPS.Items3": "60 FPS(推荐)",
    "CmbReplaySave.Items": "仅通关时保存",
    "CmbReplaySave.Items1": "仅通关和游戏结束时保存",
    "CmbReplaySave.Items2": "总是保存(默认)",
    "ExecuteUpdater.Text": "检查更新",
    "JoyStickGroup.Text": "游戏手柄",
    "LblJoyRapid.Text": "连射：",
    "LblJoyShot.Text": "射击：",
    "LblJoyShotSub.Text": "长按锁定射击",
    "SoundGroup.Text": "声音设置",
    "TwitterGroup.Text": "Twitter设置",
    "label1.Text": "画面尺寸：",
    "label11.Text": "使用的手柄：",
    "label14.Text": "概念反应堆：",
    "label15.Text": "低速移动：",
    "label16.Text": "菜单：",
    "label2.Text": "玩家名：",
    "label3.Text": "录像保存：",
    "label4.Text": "语言：",
    # 保留原文：CmbLanguage.Items（日本語/English）、label13（M.E.F.A2：）、label6（FPS：）
}
PROPS = {
    "CmbDisplaySizeItem1": "640 x 480 px(标准)",
    "ConflictAssignment": "手柄设置中存在重复的按键。",
    "Error": "错误",
    "ErrorPlayerName": "玩家名只能使用半角字符",
    "ExeNotFound": "未找到游戏主程序\"{0}\"。",
    "FailedToLaunch": "启动游戏失败。\r\n错误信息：{0}",
    "FailedToUpdate": "启动更新程序失败。",
    "Notice": "提示",
    "Save": "设置已保存到{0}。",
    "SaveAndLaunch": "设置已保存到{0}。\r\n正在启动游戏…",
    "TwitterNotFound": "未找到 sstwitter.exe。\r\n错误信息：{0}",
    "WritingError": "无法写入配置文件\"{0}\"。\r\n请检查文件是否为只读。",
}
PROPS_EN = dict(PROPS, CmbDisplaySizeItem1="640 x 480 px(默认)")
FRM_EN = dict(FRM)
TMAPS = {"PROPS": PROPS, "PROPS_EN": PROPS_EN, "FRM": FRM, "FRM_EN": FRM_EN}

# ---------------- .resources v2 解析/重建 ----------------
def read7(b, p):
    v = 0; s = 0
    while True:
        x = b[p]; p += 1
        v |= (x & 0x7f) << s
        if not (x & 0x80): return v, p
        s += 7

def write7(v):
    out = bytearray()
    while True:
        x = v & 0x7f; v >>= 7
        if v: out.append(x | 0x80)
        else: out.append(x); return bytes(out)

def read_lenstr(b, p):
    n, p = read7(b, p)
    return b[p:p+n].decode("utf-8"), p+n

def parse(d, off):
    """解析位于 d[off:] 的 .resources 块，返回 (dsoff, entries)。
    entries: [(name, name_off_abs, name_len, data_off, type_code, str_value_or_None, raw_abs_start)]"""
    assert struct.unpack_from("<I", d, off)[0] == 0xBEEFCACE, "magic 不符"
    p = off + 12
    _, p = read_lenstr(d, p)
    _, p = read_lenstr(d, p)
    ver, nres, ntypes = struct.unpack_from("<iii", d, p)
    assert ver == 2, "版本不符"
    p += 12
    for _ in range(ntypes):
        _, p = read_lenstr(d, p)
    q = off + ((p - off + 7) & ~7)          # PAD 对齐相对块起点
    pos_pos = q + 4*nres
    dsoff_pos = pos_pos + 4*nres
    dsoff = struct.unpack_from("<i", d, dsoff_pos)[0]
    name_base_abs = dsoff_pos + 4
    positions = struct.unpack_from("<%di" % nres, d, pos_pos)
    entries = []
    for pos in sorted(positions):
        np_ = name_base_abs + pos
        nlen, np2 = read7(d, np_)          # 7 位长度 = UTF-16LE 名字字节数
        name = d[np2:np2+nlen].decode("utf-16-le")
        name_len = np2 + nlen - np_         # 长度前缀 + 名字
        data_off = struct.unpack_from("<i", d, np2 + nlen)[0]
        dp = off + dsoff + data_off
        tc, dp2 = read7(d, dp)
        val = None
        if tc == 1:
            vlen, dp3 = read7(d, dp2)
            val = d[dp3:dp3+vlen].decode("utf-8")
        entries.append([name, np_, name_len, data_off, tc, val, dp])
    entries.sort(key=lambda e: e[3])        # 按数据偏移排序（数据区布局顺序）
    return dsoff, entries

def rebuild(d, off, dsoff, entries, tmap, blob_len):
    """字符串按翻译表替换后原位重打包，返回等长的新块字节。
    非字符串条目（图片/尺寸等）按原字节拷贝，范围由相邻条目偏移推算。"""
    new_data = bytearray()
    new_off = {}
    for i, e in enumerate(entries):          # entries 已按 data_off 排序
        name, _, _, _, tc, val, raw_start = e
        new_off[name] = len(new_data)
        if tc == 1:
            v = tmap.get(name, val)
            vb = v.encode("utf-8")
            new_data += b"\x01" + write7(len(vb)) + vb
        else:
            raw_end = entries[i+1][6] if i + 1 < len(entries) else off + blob_len
            new_data += d[raw_start:raw_end]
    if len(new_data) > blob_len - dsoff:
        raise RuntimeError("资源块超出原大小")
    out = bytearray(d[off:off+dsoff])        # 头部+名字区原样
    out += new_data
    out += b"\x00" * (blob_len - len(out))
    assert len(out) == blob_len
    for e in entries:                        # 回填每条名字后的 4 字节数据偏移
        name, name_off, name_len, _, _, _, _ = e
        struct.pack_into("<i", out, name_off + name_len - off, new_off[name])
    return bytes(out)

# ---------------- 主流程 ----------------
def main():
    exe = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.exe")
    if len(sys.argv) > 1:
        exe = sys.argv[1]
    if not os.path.exists(exe):
        print("错误：找不到 config.exe（%s）" % exe); return 1
    d = open(exe, "rb").read()
    if len(d) != FILESIZE:
        print("错误：config.exe 大小不符（%d ≠ %d），版本可能不同，已取消。" % (len(d), FILESIZE)); return 1
    sha = hashlib.sha256(d).hexdigest()
    if sha == PATCHED_SHA256:
        print("config.exe 已打过中文补丁，无需重复操作。"); return 0
    if sha != ORIG_SHA256:
        print("错误：config.exe 校验不符（SHA-256 不匹配），版本可能不同，已取消。"); return 1

    bak = exe + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(exe, bak)
        print("已备份原始文件 -> config.exe.bak")
    else:
        print("config.exe.bak 已存在，保留原备份")

    out = bytearray(d)
    for off, size, tag in BLOBS:
        tmap = TMAPS[tag]
        dsoff, entries = parse(d, off)
        names = {e[0] for e in entries}
        missing = [k for k in tmap if k not in names]
        if missing:
            print("错误：%s 块缺少预期键：%s" % (tag, missing)); return 1
        nb = rebuild(d, off, dsoff, entries, tmap, size)
        out[off:off+size] = nb
        print("%-8s 偏移 0x%05x  %6d 字节  替换 %d 条文本" % (tag, off, size, len(tmap)))
    assert len(out) == len(d)
    open(exe, "wb").write(bytes(out))
    print("完成！config.exe 已汉化。")
    return 0

if __name__ == "__main__":
    sys.exit(main())
