# MouseFX（Windows 鼠标点击特效）

本项目专注于：
- 全局捕获鼠标左键点击并显示可配置的点击/拖拽特效（爱心、星星、小花、彩纸、钱币等）。
- 通过 `config.json` 调整特效效果、颜色、数量、持续时间与热键。
- 支持打包为 Windows EXE。

## 功能特性
- 点击特效（可多选并随机）：
  - heart（心形爆炸，多彩）
  - star（星星散射）
  - bubble（气泡上浮）
  - ripple（波纹扩散）
  - confetti（彩带烟花）
  - ......(其他特效)
- 全局热键：
 - `Ctrl+Alt+H` 显示/隐藏特效层，
 - `Ctrl+Alt+Q` 退出。

## 快速开始（开发）

1. 安装 Python 3.10+（64位）。
2. 安装依赖：

```powershell
pip install -r requirements.txt
```

3. 运行：

```powershell
python src/main.py
```

4. 修改配置：编辑根目录的 `config.json`。

## 打包为 EXE

推荐使用 PyInstaller（可指定自定义图标）：

```powershell
pyinstaller --noconfirm --onefile --noconsole --icon "ico\\firefox.ico" src/main.py
```

- 生成的 EXE 位于 `dist/`。
- 如果你希望减少杀软误报，可改用 `--onedir`，或签名可执行文件。

## 配置说明（config.json）

```json
{
  "effects": {
    "enabled": true,
    "global": true,
    "types": ["heart", "star", "bubble", "ripple", "confetti"],
    "randomPick": true,
    "density": 6, // 粒子数量级，越大越密
    "duration": 1.6, // 秒
    "colors": ["#FF5252", "#FF4081", "#E040FB", "#7C4DFF", "#536DFE", "#448AFF", "#40C4FF", "#18FFFF", "#64FFDA", "#69F0AE"],
    "sizeRange": [14, 28],
    "speedRange": [150, 420] // 速度/散射半径
  },
  "hotkeys": {
    "toggleEffects": "ctrl+alt+h",
    "quit": "ctrl+alt+q"
  }
}
```

##  版本发布（Release）
- windows64应用程序：`dist/MouseFX-V1.0-Win64.exe`
- 随附文件：请将根目录的 `config.json` 与 `ico/` 一并放到可执行文件同目录，用户即可修改配置与替换图标。



## 兼容性与限制
- 需要 Windows 10/11。
- 部分安全软件可能阻止窗口注入或全局钩子，请将程序加入白名单。

## 开发笔记
- 使用 PySide6 创建透明点击穿透的全屏窗口渲染特效层。
- 全局鼠标监听使用 pynput。

## 许可证
PolyForm Noncommercial License 1.0.0（仅限非商业使用）
