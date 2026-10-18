# -*- coding: utf-8 -*-
"""Translate config.exe's embedded .NET resources to Simplified Chinese (in-place, same blob sizes)."""
import sys, shutil
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, r"D:\Steam\steamapps\common\RefRain - prism memories -\modtools")
import reslib

GAME = r"D:\Steam\steamapps\common\RefRain - prism memories -"
CN = GAME + r"\modtools\cnres"

# ---------- translations ----------
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
    # keep as-is: CmbLanguage.Items (日本語/English), label13 M.E.F.A2：, label6 FPS：, Lbl*Volume "100 %"
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
PROPS_EN_FALLBACK = {  # .en overrides: same Chinese (a few keys differ in en only by wording)
    "CmbDisplaySizeItem1": "640 x 480 px(默认)",
}
FRM_EN_ONLY = {  # only in en blob
    "LblJoyShotSub.Text": "长按锁定射击",  # same as ja, harmless
}
# en blobs use the same Chinese text for all shared keys
PROPS_EN = dict(PROPS); PROPS_EN.update(PROPS_EN_FALLBACK)
FRM_EN = dict(FRM); FRM_EN.update(FRM_EN_ONLY)

JOBS = [
    (CN + r"\Config.Properties.Resources.resources",       PROPS),
    (CN + r"\Config.Properties.Resources.en.resources",    PROPS_EN),
    (CN + r"\RefRainConfig.FrmMain.resources",             FRM),
    (CN + r"\RefRainConfig.FrmMain.en.resources",          FRM_EN),
]

exe = open(GAME + r"\config.exe", "rb").read()
orig_exe = exe
changed = bytearray(exe)
report = []
for path, tmap in JOBS:
    data = open(path, "rb").read()
    rf = reslib.ResFile(data)
    missing = [k for k in tmap if rf.get(k) is None]
    if missing:
        raise SystemExit(f"{path}: keys not found: {missing}")
    # per-key growth report
    grow = sum(len(tmap[e.name].encode()) - len(e.value.encode()) for e in rf.entries if e.name in tmap)
    out = reslib.rebuild(rf, tmap, len(data))
    assert len(out) == len(data)
    off = exe.find(data)
    if off < 0:
        raise SystemExit(f"{path}: original blob bytes not found in config.exe!")
    # ensure only one occurrence
    if exe.find(data, off+1) >= 0:
        raise SystemExit(f"{path}: blob bytes appear multiple times!")
    changed[off:off+len(data)] = out
    report.append((path.split("\\")[-1], len(data), off, grow))
    print(f"patched {path.split(chr(92))[-1]:45s} blob={len(data):6d}B @ exe 0x{off:x}  string-delta={grow:+d}B")

assert len(changed) == len(exe)
open(GAME + r"\config.exe", "wb").write(bytes(changed))
print("\nconfig.exe written OK (%d bytes)" % len(changed))
