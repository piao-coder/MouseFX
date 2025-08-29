import json
import sys
import os
import logging
from PySide6 import QtCore, QtGui, QtWidgets
from pynput import mouse

from effects import EffectLayer
from win_util import set_window_click_through, WM_HOTKEY, RegisterHotKey, UnregisterHotKey, parse_hotkey_to_vk

# logging 配置：默认 WARNING 以上，允许通过 config.json 的 debug 字段开启 DEBUG
logger = logging.getLogger(__name__)

logging.basicConfig(level=logging.WARNING, format='[%(levelname)s] %(message)s')

# 安装 Qt 消息处理器，过滤特定底层 API 的重复错误日志，避免控制台刷屏
def _qt_message_handler(msg_type, context, message):
    try:
        text = str(message)
        if 'UpdateLayeredWindowIndirect failed' in text:
            return  # 静默这些重复的底层错误信息
    except Exception:
        pass
    # 其它信息仍打印到 stderr，便于调试
    import sys as _sys
    _sys.stderr.write(str(message) + '\n')

QtCore.qInstallMessageHandler(_qt_message_handler)

# 在创建 QApplication 之前启用高 DPI 感知，避免坐标在缩放环境下错位
def _enable_per_monitor_dpi_awareness():
    try:
        import ctypes
        user32 = ctypes.windll.user32
        # Windows 10+ 优先使用 PMv2
        try:
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = ctypes.c_void_p(-4)
            user32.SetProcessDpiAwarenessContext.restype = ctypes.c_bool
            if user32.SetProcessDpiAwarenessContext(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2):
                return
        except Exception:
            pass
        # 其次尝试 shcore.SetProcessDpiAwareness
        try:
            shcore = ctypes.windll.shcore
            # 2 = PROCESS_PER_MONITOR_DPI_AWARE
            shcore.SetProcessDpiAwareness(2)
            return
        except Exception:
            pass
        # 最后退化为 SetProcessDPIAware（系统级）
        try:
            user32.SetProcessDPIAware()
        except Exception:
            pass
    except Exception:
        pass

# 设置界面
class SettingsWindow(QtWidgets.QWidget):
    def __init__(self, config, on_save):
        super().__init__()
        self.setWindowTitle("桌面美化设置（By:josn_deng）")
        self.config = config
        self.on_save = on_save
        layout = QtWidgets.QVBoxLayout(self)

    # 壁纸功能已移除（动态壁纸相关代码已删除）

        # 特效设置
        group_effects = QtWidgets.QGroupBox("鼠标点击特效")
        eff_layout = QtWidgets.QFormLayout(group_effects)
        self.eff_enabled = QtWidgets.QCheckBox("启用点击特效")
        self.eff_enabled.setChecked(config['effects'].get('enabled', True))
        eff_layout.addRow(self.eff_enabled)
        self.eff_performance = QtWidgets.QCheckBox("性能优化模式（降低特效质量以提升性能）")
        self.eff_performance.setChecked(config['effects'].get('performanceMode', True))
        eff_layout.addRow(self.eff_performance)
        self.eff_types = {}
        type_defs = [("heart", "爱心"), ("star", "星星"), ("ripple", "小花"), ("confetti", "彩纸"), ("coin", "钱币")]
        default_types = [k for k, _ in type_defs]
        type_layout = QtWidgets.QHBoxLayout()
        for key, label in type_defs:
            cb = QtWidgets.QCheckBox(label)
            cb.setChecked(key in config['effects'].get('types', default_types))
            self.eff_types[key] = cb
            type_layout.addWidget(cb)
        eff_layout.addRow("特效类型", type_layout)
        self.eff_density = QtWidgets.QSpinBox()
        self.eff_density.setRange(1, 20)
        self.eff_density.setValue(config['effects'].get('density', 6))
        eff_layout.addRow("分裂数量", self.eff_density)
        self.eff_duration = QtWidgets.QDoubleSpinBox()
        self.eff_duration.setRange(0.5, 5.0)
        self.eff_duration.setValue(config['effects'].get('duration', 1.6))
        eff_layout.addRow("持续时间", self.eff_duration)
        self.eff_colors = QtWidgets.QLineEdit(",".join(config['effects'].get('colors', [])))
        eff_layout.addRow("颜色(逗号分隔)", self.eff_colors)
        layout.addWidget(group_effects)

        # 拖拽轨迹设置
        group_trail = QtWidgets.QGroupBox("拖拽轨迹")
        trail_layout = QtWidgets.QFormLayout(group_trail)
        self.trail_enabled = QtWidgets.QCheckBox("启用拖拽轨迹")
        self.trail_enabled.setChecked(config['effects'].get('trailEnabled', True))
        trail_layout.addRow(self.trail_enabled)
        self.trail_density = QtWidgets.QSpinBox()
        self.trail_density.setRange(1, 20)
        self.trail_density.setValue(config['effects'].get('trailDensity', 2))
        trail_layout.addRow("轨迹密度", self.trail_density)
        self.trail_life = QtWidgets.QDoubleSpinBox()
        self.trail_life.setRange(0.1, 2.0)
        self.trail_life.setSingleStep(0.1)
        self.trail_life.setValue(float(config['effects'].get('trailLife', 0.5)))
        trail_layout.addRow("光点寿命(s)", self.trail_life)
        self.trail_min_interval = QtWidgets.QSpinBox()
        self.trail_min_interval.setRange(1, 50)
        self.trail_min_interval.setValue(int(config['effects'].get('trailMinIntervalMs', 18)))
        trail_layout.addRow("最小间隔(ms)", self.trail_min_interval)
        self.trail_size_min = QtWidgets.QSpinBox(); self.trail_size_min.setRange(1, 50)
        self.trail_size_max = QtWidgets.QSpinBox(); self.trail_size_max.setRange(1, 80)
        size_rng = config['effects'].get('trailSizeRange', [5, 10])
        self.trail_size_min.setValue(int(size_rng[0]))
        self.trail_size_max.setValue(int(size_rng[1]))
        hl_size = QtWidgets.QHBoxLayout(); hl_size.addWidget(self.trail_size_min); hl_size.addWidget(QtWidgets.QLabel(" - ")); hl_size.addWidget(self.trail_size_max)
        trail_layout.addRow("光点尺寸", hl_size)
        self.trail_flower_chance = QtWidgets.QDoubleSpinBox()
        self.trail_flower_chance.setRange(0.0, 1.0)
        self.trail_flower_chance.setSingleStep(0.05)
        self.trail_flower_chance.setValue(float(config['effects'].get('trailFlowerChance', 0.25)))
        trail_layout.addRow("花瓣概率", self.trail_flower_chance)
        self.trail_flower_min = QtWidgets.QSpinBox(); self.trail_flower_min.setRange(1, 60)
        self.trail_flower_max = QtWidgets.QSpinBox(); self.trail_flower_max.setRange(1, 80)
        frng = config['effects'].get('trailFlowerSizeRange', [8, 14])
        self.trail_flower_min.setValue(int(frng[0]))
        self.trail_flower_max.setValue(int(frng[1]))
        hl_fr = QtWidgets.QHBoxLayout(); hl_fr.addWidget(self.trail_flower_min); hl_fr.addWidget(QtWidgets.QLabel(" - ")); hl_fr.addWidget(self.trail_flower_max)
        trail_layout.addRow("花瓣尺寸", hl_fr)
        layout.addWidget(group_trail)

        # 热键设置
        group_hotkey = QtWidgets.QGroupBox("热键设置")
        hot_layout = QtWidgets.QFormLayout(group_hotkey)
        self.hk_toggle = QtWidgets.QLineEdit(config['hotkeys'].get('toggleEffects', 'ctrl+alt+h'))
        hot_layout.addRow("特效开关", self.hk_toggle)
        self.hk_quit = QtWidgets.QLineEdit(config['hotkeys'].get('quit', 'ctrl+alt+q'))
        hot_layout.addRow("退出程序", self.hk_quit)
        layout.addWidget(group_hotkey)

        # 保存按钮
        btn_save = QtWidgets.QPushButton("保存设置并应用")
        btn_save.clicked.connect(self.save)
        layout.addWidget(btn_save)

    # 一键性能优先功能已移除

    # 壁纸选择功能已移除

    def save(self):
    # 更新配置（壁纸功能已移除）
        self.config['effects']['enabled'] = self.eff_enabled.isChecked()
        self.config['effects']['performanceMode'] = self.eff_performance.isChecked()
        self.config['effects']['types'] = [t for t, cb in self.eff_types.items() if cb.isChecked()]
        self.config['effects']['density'] = self.eff_density.value()
        self.config['effects']['duration'] = self.eff_duration.value()
        self.config['effects']['colors'] = [c.strip() for c in self.eff_colors.text().split(",") if c.strip()]
        # 拖拽轨迹参数
        self.config['effects']['trailEnabled'] = self.trail_enabled.isChecked()
        self.config['effects']['trailDensity'] = self.trail_density.value()
        self.config['effects']['trailLife'] = float(self.trail_life.value())
        self.config['effects']['trailMinIntervalMs'] = self.trail_min_interval.value()
        self.config['effects']['trailSizeRange'] = [self.trail_size_min.value(), self.trail_size_max.value()]
        self.config['effects']['trailFlowerChance'] = float(self.trail_flower_chance.value())
        self.config['effects']['trailFlowerSizeRange'] = [self.trail_flower_min.value(), self.trail_flower_max.value()]
        self.config['hotkeys']['toggleEffects'] = self.hk_toggle.text()
        self.config['hotkeys']['quit'] = self.hk_quit.text()
        # 保存到 config.json
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(__file__))
        cfg_path = os.path.join(exe_dir, 'config.json')
        with open(cfg_path, 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)
        QtWidgets.QMessageBox.information(self, "设置", "设置已保存并应用！")
        self.on_save()
        self.close()


class App(QtWidgets.QApplication):
    def __init__(self, argv):
        super().__init__(argv)
        # 初始应用名，稍后按配置覆盖
        QtCore.QCoreApplication.setApplicationName("MouseFX")
        self.setQuitOnLastWindowClosed(False)

        # 加载配置：优先使用可执行文件所在目录，其次 _MEIPASS，最后源码根目录
        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
        else:
            exe_dir = os.path.dirname(os.path.dirname(__file__))
        cfg_path = os.path.join(exe_dir, 'config.json')
        if not os.path.exists(cfg_path):
            base_dir = getattr(sys, '_MEIPASS', exe_dir)
            cfg_path = os.path.join(base_dir, 'config.json')
        with open(cfg_path, 'r', encoding='utf-8') as f:
            self.config = json.load(f)

        # 应用通用配置（应用名 / 图标 / AppUserModelID）
        self.config.setdefault('app', {})
        app_name = self.config['app'].get('name', 'MouseFX')
        try:
            QtCore.QCoreApplication.setApplicationName(app_name)
            QtCore.QCoreApplication.setApplicationDisplayName(app_name)
        except Exception:
            pass
        # 设置 Windows AppUserModelID，确保任务栏分组与图标正确
        aumid = self.config['app'].get('appUserModelId', f"{app_name}.App")
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(ctypes.c_wchar_p(aumid))
        except Exception:
            pass

        # 根据配置启用 DEBUG 日志
        if self.config.get('debug', False):
            logging.getLogger().setLevel(logging.DEBUG)

        # 设置界面（首次启动显示一次，可通过托盘再次打开）
        self.settings_win = SettingsWindow(self.config, self.apply_settings)
        # 应用图标
        self._icon = self._load_icon()
        try:
            self.setWindowIcon(self._icon)
            self.settings_win.setWindowIcon(self._icon)
        except Exception:
            pass
        self.settings_win.show()

        # 特效层
        self.overlay = EffectLayer(self.config)
        self.overlay.show()
        # 全局鼠标监听（点击 + 移动）
        self._left_pressed = False
        self.listener = mouse.Listener(on_click=self.on_click, on_move=self.on_move)
        self.listener.start()
        logger.debug("mouse listener started: %s", self.listener)

        # 热键（注册全局热键 + 处理 WM_HOTKEY）
        self._hotkey_ids = {}
        self._register_hotkeys()
        self._native_filter = _NativeEventFilter(self)
        self.installNativeEventFilter(self._native_filter)

        # 系统托盘
        self._init_tray()

    def _init_tray(self):
        if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("系统托盘不可用，托盘功能已禁用")
            return
        tray_icon = self._icon if hasattr(self, '_icon') and not self._icon.isNull() else self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
        self.tray = QtWidgets.QSystemTrayIcon(tray_icon, self)
        menu = QtWidgets.QMenu()
        act_open = menu.addAction("打开设置")
        act_toggle = menu.addAction("切换特效")
        
        act_toggle.setCheckable(True)
        act_toggle.setChecked(self.overlay.visible_effects)
        menu.addSeparator()
        act_quit = menu.addAction("退出")
        act_open.triggered.connect(self.open_settings)
        act_toggle.triggered.connect(self._tray_toggle_effects)
        act_quit.triggered.connect(self.quit)
        self._tray_actions = {"toggle": act_toggle}
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        try:
            self.tray.setToolTip(QtCore.QCoreApplication.applicationName())
        except Exception:
            self.tray.setToolTip("鼠标特效")
        self.tray.show()

    def _get_icon_path(self) -> str:
        # 配置优先：app.icon 可为绝对或相对路径
        icon_cfg = self.config.get('app', {}).get('icon')
        bases = []
        # 运行目录与源码目录作为基准
        bases.append(os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.dirname(__file__)))
        if icon_cfg:
            # 若为绝对路径
            if os.path.isabs(icon_cfg) and os.path.exists(icon_cfg):
                return icon_cfg
            # 尝试在各基准目录下拼接
            for b in bases:
                p = os.path.join(b, icon_cfg)
                if os.path.exists(p):
                    return p
        # 兜底到项目自带图标
        for b in bases:
            candidate = os.path.join(b, 'ico', 'firefox.ico')
            if os.path.exists(candidate):
                return candidate
        return ''

    def _load_icon(self) -> QtGui.QIcon:
        try:
            path = self._get_icon_path()
            icon = QtGui.QIcon(path)
            return icon
        except Exception:
            return QtGui.QIcon()

    def _on_tray_activated(self, reason):
        if reason == QtWidgets.QSystemTrayIcon.DoubleClick:
            self.open_settings()

    def open_settings(self):
        try:
            if self.settings_win is None or not self.settings_win.isVisible():
                self.settings_win = SettingsWindow(self.config, self.apply_settings)
                try:
                    self.settings_win.setWindowIcon(self._icon)
                except Exception:
                    pass
                self.settings_win.show()
            else:
                self.settings_win.showNormal()
                self.settings_win.raise_()
                self.settings_win.activateWindow()
        except Exception:
            # 兜底：重建一个
            self.settings_win = SettingsWindow(self.config, self.apply_settings)
            try:
                self.settings_win.setWindowIcon(self._icon)
            except Exception:
                pass
            self.settings_win.show()

    def _tray_toggle_effects(self):
        self.overlay.toggle()
        self._sync_tray_state()

    def _sync_tray_state(self):
        act_toggle = getattr(self, "_tray_actions", {}).get("toggle")
        if act_toggle:
            act_toggle.setChecked(self.overlay.visible_effects)

    # 动态壁纸功能已移除；不再提供托盘切换壁纸

    def apply_settings(self):
        # 重新应用特效设置
        self.overlay.update_config(self.config)
        self.overlay.visible_effects = self.config['effects'].get('enabled', True)
        self._sync_tray_state()
        # 重新注册热键
        for hid in getattr(self, '_hotkey_ids', {}).keys():
            try:
                UnregisterHotKey(0, hid)
            except Exception:
                pass
        self._hotkey_ids = {}
        self._register_hotkeys()

    def _register_hotkeys(self):
        # 全局热键
        hid = 1
        for name, hk in self.config.get('hotkeys', {}).items():
            mods, vk = parse_hotkey_to_vk(hk)
            if mods and vk:
                RegisterHotKey(0, hid, mods, vk)
                self._hotkey_ids[hid] = name
                hid += 1

    def on_click(self, x, y, button, pressed):
        if not pressed:
            # 松开时清理按下状态
            try:
                is_left = (button.name == 'left')
            except Exception:
                is_left = (str(button) == 'Button.left')
            if is_left:
                self._left_pressed = False
            return
        try:
            logger.debug("on_click pressed at %s,%s button=%s pressed=%s", x, y, button, pressed)
        except Exception as e:
            logger.exception("on_click print error: %s", e)
        # 左键
        try:
            is_left = (button.name == 'left')
        except Exception:
            is_left = (str(button) == 'Button.left')
        if is_left:
            self._left_pressed = True
            # 使用 Qt 的全局鼠标位置（逻辑坐标），避免与 pynput 的物理像素产生缩放偏差
            qpos = QtGui.QCursor.pos()
            logger.debug("detected left click -> spawning effects at %s,%s (qt=%s,%s)", x, y, qpos.x(), qpos.y())
            self.overlay.spawn(int(qpos.x()), int(qpos.y()))

    def on_move(self, x, y):
        # 左键长按滑动轨迹特效
        if getattr(self, '_left_pressed', False):
            # 用 Qt 逻辑坐标保证与绘制坐标系一致
            qpos = QtGui.QCursor.pos()
            self.overlay.spawn_trail(int(qpos.x()), int(qpos.y()))

    def handle_hotkey(self, name: str):
        if name == 'toggleEffects':
            self.overlay.toggle()
            self._sync_tray_state()
        elif name == 'quit':
            self.quit()

    def quit(self):
        # 清理资源
        # 反注册
        for hid in getattr(self, '_hotkey_ids', {}).keys():
            try:
                UnregisterHotKey(0, hid)
            except Exception:
                pass
        super().quit()


class _NativeEventFilter(QtCore.QAbstractNativeEventFilter):
    def __init__(self, app: App):
        super().__init__()
        self.app = app

    def nativeEventFilter(self, eventType, message):
        if eventType != 'windows_generic_MSG':
            return False, 0
        from ctypes import wintypes, windll, byref
        import ctypes
        msg = ctypes.wintypes.MSG.from_address(int(message))
        if msg.message == WM_HOTKEY:
            hid = msg.wParam
            name = self.app._hotkey_ids.get(hid)
            if name:
                QtCore.QTimer.singleShot(0, lambda n=name: self.app.handle_hotkey(n))
        return False, 0


# 本项目仅包含鼠标点击/拖拽特效，已不包含任何动态壁纸相关代码。


if __name__ == '__main__':
    # 必须在 QApplication 创建之前设置 DPI 策略与属性
    try:
        # 对位图/图标启用高 DPI 资源
        QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass
    _enable_per_monitor_dpi_awareness()
    app = App(sys.argv)
    sys.exit(app.exec())
