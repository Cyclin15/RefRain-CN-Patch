# RefRain - prism memories - 简体中文汉化补丁

《RefRain - prism memories -》（RebRank 出品，Steam 上的免费纵版弹幕射击游戏）的非官方简体中文汉化补丁。

汉化覆盖游戏内全部 949 行文本（943 行译文；其余 6 行原文即为空行或开发组故意保留的乱码彩蛋）。

## 下载与安装

从 [Releases](https://github.com/Cyclin15/RefRain-CN-Patch/releases) 下载最新的 `RefRain-CN-Patch.zip`，然后：

1. 解压压缩包内所有文件到游戏根目录（`RefRain.exe` 所在的目录，保留 `Patch` 文件夹结构）。
2. 双击运行 `安装exe补丁.bat`。它会：
   - 把原版 `RefRain.exe` 备份为 `RefRain.exe.bak`；
   - 修改主程序中的 1 个字节（GDI 字体字符集：日文 Shift-JIS → 简体中文 GB2312）。
3. 启动游戏即可。

### 环境要求

- Steam 版《RefRain - prism memories -》V1.03.7（`RefRain.exe` 大小 1,118,160 字节）；
- 简体中文区域设置的 Windows（系统代码页 GBK / 936）——本补丁利用 GBK 代码页直接显示中文，非中文区域设置下无法正常显示。

### 卸载

- 删除 `Patch\patch_0001.rp1`；
- 把 `RefRain.exe.bak` 改名回 `RefRain.exe`（或通过 Steam 校验游戏文件还原主程序）。

### 常见问题

- **游戏内乱码 / 方块字**：确认系统区域设置为简体中文。
- **bat 提示版本不符**：本补丁仅支持 V1.03.7 版主程序。
- **Steam 校验文件后汉化失效**：校验会还原主程序，重新运行一次 `安装exe补丁.bat` 即可。

## 工作原理

游戏通过 `rp1` 补丁包机制（`Patch\patch_0001.rp1`，type 0x10）加载覆盖资源，官方格式本身支持替换 `localization.rsr`（TSV：`MSG编号\t日文\t英文`，游戏默认读取英文列）。汉化做了两件事：

1. **文本**：把 `localization.rsr` 的英文列替换为 GBK 编码的中文译文；
2. **字体**：补丁包内嵌一份改名为游戏默认字体名的 [Noto Sans SC](https://fonts.google.com/noto/specimen/Noto+Sans+SC)（OFL 1.1）子集，配合主程序那 1 字节的字符集补丁，让 GDI 用 GB2312 字符集正确渲染中文。

`tools/` 目录是本补丁的全部构建脚本（Python 3，依赖 fontTools）：

- `cn/part1.py` … `cn/part7_music.py` —— 全部译文（按文本行号分段）；
- `buildfont.py` —— 从 Noto Sans SC 变量字体实例化 wght=500、子集化并改写字体名表；
- `smokebuild.py` / `finalbuild.py` —— 生成 `localization.rsr` 并打包 `patch_0001.rp1`；
- `packrp1.py` / `raf1.py` —— rp1 包打包器与格式解析/模拟器；
- `gditest.py` —— 用 GDI 预验证字体渲染；
- `bisecttest.py` —— 二分排查崩溃行的自动化工具。

在游戏根目录下运行 `python tools/finalbuild.py` 即可重新构建 `Patch\patch_0001.rp1`（脚本内含各文件的路径约定）。

## 致谢与版权

- 本补丁为非官方同人汉化，与 RebRank 无关；仅供学习交流，游戏本体请到 [Steam 商店页](https://store.steampowered.com/app/314810/) 支持正版。
- 内嵌字体基于 [Google Noto Sans SC](https://fonts.google.com/noto/specimen/Noto+Sans+SC)，依 [SIL Open Font License 1.1](OFL.txt) 授权再分发。
- 《RefRain - prism memories -》© RebRank。
