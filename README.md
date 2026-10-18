# RefRain - prism memories - 简体中文汉化补丁

《RefRain - prism memories -》（RebRank 出品，Steam 上的免费纵版弹幕射击游戏）的非官方简体中文汉化补丁。

汉化覆盖游戏内全部 949 行文本（943 行译文；其余 6 行原文即为空行或开发组故意保留的乱码彩蛋）、教学关（TUTORIAL）的全部界面图文（对话、开始/跳过菜单、章节标题、任务目标、计量槽标签等 106 处精灵文本），并可选地汉化启动配置工具 `config.exe` 的界面。

## 下载与安装

从 [Releases](https://github.com/Cyclin15/RefRain-CN-Patch/releases) 下载最新的 `RefRain-CN-Patch.zip`，然后：

1. 解压压缩包内所有文件到游戏根目录（`RefRain.exe` 所在的目录，保留 `Patch` 文件夹结构）。
2. 双击运行 `安装exe补丁.bat`。它会：
   - 把原版 `RefRain.exe` 备份为 `RefRain.exe.bak`；
   - 修改主程序中的 1 个字节（GDI 字体字符集：日文 Shift-JIS → 简体中文 GB2312）。
3. 启动游戏即可。
4. （可选）双击运行 `安装config补丁.bat`，把 `config.exe` 设置界面（画面尺寸、音量、手柄、Twitter 等全部选项）也汉化为中文。这一步需要安装 [Python 3](https://www.python.org/)（安装时勾选 "Add python.exe to PATH"）；没有 Python 也不影响游戏本体汉化，只是配置工具保持原样。

### 环境要求

- Steam 版《RefRain - prism memories -》V1.03.7（`RefRain.exe` 大小 1,118,160 字节）；
- 简体中文区域设置的 Windows（系统代码页 GBK / 936）——本补丁利用 GBK 代码页直接显示中文，非中文区域设置下无法正常显示；
- （仅 config.exe 汉化需要）Python 3。

### 卸载

- 删除 `Patch\patch_0001.rp1`；
- 把 `RefRain.exe.bak` 改名回 `RefRain.exe`（或通过 Steam 校验游戏文件还原主程序）；
- 若安装过 config 补丁：把 `config.exe.bak` 改名回 `config.exe`。

### 常见问题

- **游戏内乱码 / 方块字**：确认系统区域设置为简体中文。
- **bat 提示版本不符**：本补丁仅支持 V1.03.7 版主程序。
- **Steam 校验文件后汉化失效**：校验会还原主程序，重新运行一次 `安装exe补丁.bat` 即可。
- **config 补丁提示"未找到 Python"**：安装 Python 3 后重试，或跳过此步（不影响游戏本体）。

## 工作原理

游戏通过 `rp1` 补丁包机制（`Patch\patch_0001.rp1`，type 0x10）加载覆盖资源，官方格式本身支持替换 `localization.rsr`（TSV：`MSG编号\t日文\t英文`，游戏默认读取英文列）。汉化做了三件事：

1. **文本**：把 `localization.rsr` 的英文列替换为 GBK 编码的中文译文；
2. **字体**：补丁包内嵌一份改名为游戏默认字体名的 [Noto Sans SC](https://fonts.google.com/noto/specimen/Noto+Sans+SC)（OFL 1.1）子集，配合主程序那 1 字节的字符集补丁，让 GDI 用 GB2312 字符集正确渲染中文；
3. **教学关图文**：教学关的界面文字预渲染在贴图 `Data/Grp/tutorial_obj_eng.png` 里（113 处文字精灵，由 `Data/Script/tutorial.rsr` 内的精灵表引用），不走 `localization.rsr`。补丁按精灵表坐标原位擦除英文、用 Noto Sans SC 重绘中文，保留原图的配色（正文白 + 关键词黄、标题金色渐变 + 下划线、菜单灰/黄两态）与装饰图形（波纹、箭头、目标标记等），再经 rp1 覆盖同名文件。

`tools/` 目录是本补丁的全部构建脚本（Python 3，依赖 fontTools）：

- `cn/part1.py` … `cn/part7_music.py` —— 全部译文（按文本行号分段）；
- `tutorial/translation.py` —— 教学关 106 处精灵文本的译文与配色/样式表；
- `tutorial/redraw.py` / `tutorial/sprites.json` —— 教学关贴图原位重绘器与精灵表
  （自动从 `Data.ra1` 提取原图，重绘输出 `tutorial_obj_chn.png`）；
- `buildfont.py` —— 从 Noto Sans SC 变量字体实例化 wght=500、子集化并改写字体名表；
- `smokebuild.py` / `finalbuild.py` —— 生成 `localization.rsr` 并打包 `patch_0001.rp1`；
- `packrp1.py` / `raf1.py` —— rp1 包打包器与格式解析/模拟器；
- `gditest.py` —— 用 GDI 预验证字体渲染；
- `bisecttest.py` —— 二分排查崩溃行的自动化工具；
- `reslib.py` —— .NET `.resources` v2 二进制格式的解析器/重建器（逆向所得）；
- `patch_config.py` / `cn_config_patch.py` —— config.exe 汉化的开发版 / 发布版补丁器
  （发布版即 zip 内的 `cn_config_patch.py`，原理：解析 config.exe 内嵌的 4 个
  `.resources` 资源块，把 UI 字符串替换为中文后原位重打包，文件大小不变）；
- `verify_config.ps1` —— 用 .NET 自带 ResourceReader 复验打补丁后的资源；
- `ocr.ps1` / `ocr2.ps1` —— WinRT OCR 辅助脚本（开发时用于验证游戏画面）。

在游戏根目录下运行 `python tools/finalbuild.py` 即可重新构建 `Patch\patch_0001.rp1`（脚本内含各文件的路径约定）。

## 致谢与版权

- 本补丁为非官方同人汉化，与 RebRank 无关；仅供学习交流，游戏本体请到 [Steam 商店页](https://store.steampowered.com/app/314810/) 支持正版。
- 内嵌字体基于 [Google Noto Sans SC](https://fonts.google.com/noto/specimen/Noto+Sans+SC)，依 [SIL Open Font License 1.1](OFL.txt) 授权再分发。
- 《RefRain - prism memories -》© RebRank。
