from PySide6 import QtCore, QtGui, QtWidgets
import random
import math
import logging

logger = logging.getLogger(__name__)

# 粒子结构
class Particle:
    def __init__(self, pos: QtCore.QPointF, vel: QtCore.QPointF, life: float,
                 color: QtGui.QColor, text: str = "", size: float = 16.0, shape: str = "text"):
        self.pos = QtCore.QPointF(pos)
        self.vel = QtCore.QPointF(vel)
        self.life = life
        self.age = 0.0
        self.color = QtGui.QColor(color)
        self.text = text
        self.size = size
        self.shape = shape  # text|circle|star|flower|trail|rect|coin
        self.rotation = random.uniform(0, 360)
        self.spin = random.uniform(-180, 180)
        self.opacity = 1.0

    def update(self, dt: float):
        self.age += dt
        t = min(self.age / self.life, 1.0)
        # 重力与阻力
        self.vel.setY(self.vel.y() + 300 * dt)
        self.vel *= 0.98
        self.pos += self.vel * dt
        self.opacity = max(0.0, 1.0 - t)
        self.rotation += self.spin * dt

    def is_dead(self):
        return self.age >= self.life or self.opacity <= 0.05  # 提高死亡阈值，更早清除半透明粒子


class EffectLayer(QtWidgets.QWidget):
    def __init__(self, config):
        super().__init__(None, QtCore.Qt.FramelessWindowHint | QtCore.Qt.Tool | QtCore.Qt.WindowStaysOnTopHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        # 输入透明（允许鼠标穿透）
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, True)
        try:
            self.setWindowFlag(QtCore.Qt.WindowTransparentForInput, True)
        except Exception:
            pass
        self.setWindowState(QtCore.Qt.WindowFullScreen)
        self.setMouseTracking(True)
        # 初始化粒子与定时器
        self.particles = []
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.tick)
        # 上一帧的损伤区域集合（使用 QRegion 以减少整屏重绘）
        self._last_damage_region = None
        # 文字基准字体（减少频繁构造）
        self._base_font = QtGui.QFont()

        # 配置与可见性
        self.config = config
        self.visible_effects = True

        # 轨迹节流
        self._trail_clock = QtCore.QElapsedTimer()
        self._trail_clock.start()
        self._last_trail_ms = 0

        # 定期清理计时器，用于处理偶发残留
        self._cleanup_clock = QtCore.QElapsedTimer()
        self._cleanup_clock.start()
        self._last_cleanup_ms = 0

        # 性能模式与阈值
        self.performance_mode = config.get('effects', {}).get('performanceMode', False)
        self.max_particles = 200 if self.performance_mode else 300

        # 根据性能模式设置刷新间隔（10ms更流畅，33ms更省资源）
        self.last_ts = QtCore.QElapsedTimer()
        self.last_ts.start()
        # 使用高精度定时器与固定 10ms 刷新，优先保证帧率稳定
        try:
            self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        except Exception:
            pass
        self.timer.start(10)

    def showEvent(self, event):
        super().showEvent(event)
        try:
            hwnd = int(self.winId())
            logger.debug("EffectLayer.showEvent hwnd=%s", hwnd)
        except Exception:
            pass

    def toggle(self):
        self.visible_effects = not self.visible_effects
        
    def update_config(self, config):
        """更新配置并应用性能模式"""
        self.config = config
        self.performance_mode = config.get('effects', {}).get('performanceMode', False)
        self.max_particles = 200 if self.performance_mode else 300
        # 保持 10ms 刷新，确保视觉平滑
        try:
            self.timer.setTimerType(QtCore.Qt.PreciseTimer)
        except Exception:
            pass
        self.timer.setInterval(10)

    def _global_to_local(self, x: int, y: int) -> QtCore.QPointF:
        pt = self.mapFromGlobal(QtCore.QPoint(int(x), int(y)))
        return QtCore.QPointF(pt)

    def spawn(self, x: int, y: int):
        # 性能优化：如果粒子过多，跳过新的特效
        if len(self.particles) > self.max_particles:
            return
            
        if not self.visible_effects or not self.config['effects']['enabled']:
            return
        cfg = self.config['effects']
        # 基于配置的密度；在性能模式下做进一步限制
        density = int(cfg.get('density', 6))
        if self.performance_mode:
            density = min(density, 4)
        else:
            density = min(density, 24)  # 给流畅模式更高上限
        duration = float(cfg.get('duration', 1.6))
        colors = [QtGui.QColor(c) for c in cfg.get('colors', ['#FF5252'])]
        size_min, size_max = cfg.get('sizeRange', [14, 28])
        speed_min, speed_max = cfg.get('speedRange', [150, 420])
        types = cfg.get('types', ['heart'])

        picked = [random.choice(types)] if cfg.get('randomPick', True) else types
        for t in picked:
            if t == 'heart':
                self._spawn_text_burst(x, y, '❤', density, duration, colors, size_min, size_max, speed_min, speed_max)
            elif t == 'star':
                self._spawn_star(x, y, density, duration, colors, size_min, size_max, speed_min, speed_max)
            elif t == 'ripple':
                self._spawn_flower(x, y, max(4, int(density)), duration, colors, size_min, size_max, speed_min, speed_max)
            elif t == 'confetti':
                self._spawn_confetti(x, y, int(density * 1.5), duration, colors, size_min, size_max, speed_min, speed_max)
            elif t == 'coin':
                self._spawn_coin(x, y, max(4, int(density)), duration, colors, size_min, size_max, speed_min, speed_max)

    def spawn_trail(self, x: int, y: int):
        """左键长按滑动的固定轨迹特效。"""
        # 性能优化：如果粒子过多，跳过轨迹特效
        if len(self.particles) > self.max_particles * 0.8:  # 80%时开始限制轨迹
            return
            
        if not self.visible_effects or not self.config['effects'].get('enabled', True):
            return
        cfg = self.config.get('effects', {})
        if not cfg.get('trailEnabled', True):
            return
        # 读取参数
        min_interval = int(cfg.get('trailMinIntervalMs', 18))
        # 性能模式下增加间隔
        if self.performance_mode:
            min_interval = max(min_interval, 40)
            
        now = self._trail_clock.elapsed()
        if (now - self._last_trail_ms) < max(1, min_interval):
            return
        self._last_trail_ms = now
        colors = [QtGui.QColor(c) for c in cfg.get('colors', ['#FF5252', '#FFC107', '#40C4FF'])]
        base_trail_density = int(cfg.get('trailDensity', 2))
        if self.performance_mode:
            density = max(1, min(base_trail_density, 2))
        else:
            density = max(1, min(base_trail_density, 6))
            
        life = float(cfg.get('trailLife', 0.5))
        size_min, size_max = cfg.get('trailSizeRange', [5, 10])
        flower_chance = float(cfg.get('trailFlowerChance', 0.15))  # 降低花瓣概率
        flower_size_min, flower_size_max = cfg.get('trailFlowerSizeRange', [8, 14])
        pos = self._global_to_local(x, y)
        # 小光点
        for _ in range(max(1, density)):
            c = random.choice(colors)
            size = random.uniform(size_min, size_max)
            jitter = QtCore.QPointF(random.uniform(-3, 3), random.uniform(-3, 3))
            p = Particle(pos + jitter, QtCore.QPointF(0, 0), life, c, text='', size=size, shape='trail')
            p.opacity = 0.85
            self.particles.append(p)
        # 偶尔小花瓣
        if random.random() < max(0.0, min(1.0, flower_chance)):
            c = random.choice(colors)
            size = random.uniform(flower_size_min, flower_size_max)
            vel = QtCore.QPointF(random.uniform(-20, 20), random.uniform(-10, -30))
            p = Particle(pos, vel, 0.8, c, text='', size=size, shape='flower')
            p.opacity = 0.9
            self.particles.append(p)

    def _rand_vel(self, speed_min, speed_max):
        ang = random.uniform(0, math.tau)
        spd = random.uniform(speed_min, speed_max)
        return QtCore.QPointF(math.cos(ang) * spd, math.sin(ang) * spd - spd * 0.2)

    def _spawn_text_burst(self, x, y, text, count, life, colors, size_min, size_max, speed_min, speed_max):
        for _ in range(int(count)):
            vel = self._rand_vel(speed_min, speed_max)
            size = random.uniform(size_min, size_max)
            color = random.choice(colors)
            pos = self._global_to_local(x, y)
            self.particles.append(Particle(pos, vel, life, color, text=text, size=size, shape='text'))

    def _spawn_star(self, x, y, count, life, colors, size_min, size_max, speed_min, speed_max):
        for _ in range(int(count)):
            vel = self._rand_vel(speed_min, speed_max)
            size = random.uniform(size_min, size_max)
            color = random.choice(colors)
            pos = self._global_to_local(x, y)
            p = Particle(pos, vel, life, color, text='', size=size, shape='star')
            self.particles.append(p)


    def _spawn_flower(self, x, y, count, life, colors, size_min, size_max, speed_min, speed_max):
        for _ in range(int(count)):
            vel = self._rand_vel(speed_min * 0.6, speed_max * 0.9)
            size = random.uniform(size_min * 1.1, size_max * 1.6)
            color = random.choice(colors)
            pos = self._global_to_local(x, y)
            p = Particle(pos, vel, life * 1.1, color, text='', size=size, shape='flower')
            p.opacity = 0.9
            self.particles.append(p)

    def _spawn_confetti(self, x, y, count, life, colors, size_min, size_max, speed_min, speed_max):
        for _ in range(int(count)):
            vel = self._rand_vel(speed_min, speed_max * 1.2)
            size = random.uniform(size_min * 0.8, size_max * 1.2)
            color = random.choice(colors)
            pos = self._global_to_local(x, y)
            p = Particle(pos, vel, life * 1.1, color, text='', size=size, shape='rect')
            self.particles.append(p)

    def _spawn_coin(self, x, y, count, life, colors, size_min, size_max, speed_min, speed_max):
        # 钱币，支持多种货币符号
        symbols = ['￥', '$', '€', '£']
        for _ in range(int(count)):
            vel = self._rand_vel(speed_min * 0.7, speed_max * 0.9)
            size = random.uniform(size_min * 1.1, size_max * 1.6)
            symbol = random.choice(symbols)
            color = random.choice(colors)
            pos = self._global_to_local(x, y)
            p = Particle(pos, vel, life * 1.2, color, text=symbol, size=size, shape='text')
            # 动态属性
            p.opacity = 0.95
            p.spin = random.uniform(-120, 120)  # coin 旋转稍慢，显得更有分量
            self.particles.append(p)

    def tick(self):
        now = self.last_ts.elapsed() / 1000.0
        self.last_ts.restart()
        # 收紧 dt 上限，避免延迟累积导致的位移跳变（卡顿感）
        dt = max(0.001, min(now, 0.033))
        
        # 移除所有局部清理逻辑，统一全窗口重绘以确保无拖尾
        # 原代码：
        # cleanup_now = self._cleanup_clock.elapsed()
        # if (cleanup_now - self._last_cleanup_ms) > 3000:
        #     self.update()
        #     self._last_cleanup_ms = cleanup_now
        # if self._last_damage_region is not None and not self._last_damage_region.isEmpty():
        #     self.update(self._last_damage_region)
        
        # 批量更新粒子，并收集逐粒子的重绘区域（前后包围盒）
        alive_particles = []
        for p in self.particles:
            p.update(dt)
            if not p.is_dead():
                alive_particles.append(p)

        # 当粒子数量超过上限时，截断多余粒子以优化性能
        if len(alive_particles) > self.max_particles:
            alive_particles = alive_particles[-self.max_particles:]
        self.particles = alive_particles
        
        # 改为每次tick()统一全窗口重绘，确保立即清除所有残留
        self.update()
        self._last_damage_region = None

        # 减少日志输出频率
        if len(self.particles) > 0 and len(self.particles) % 50 == 0:
            logger.debug("tick: particles=%d", len(self.particles))

    def _particle_bounds(self, p: 'Particle') -> QtCore.QRect:
        # 近似包围盒：半径按尺寸放大一点，考虑旋转带来的边界增长
        if p.shape in ('text', 'star', 'rect'):
            radius = max(5.0, p.size * 0.9)
        elif p.shape == 'flower':
            radius = max(6.0, p.size * 1.2)
        elif p.shape in ('circle',):
            radius = max(5.0, p.size * 1.2)
        elif p.shape in ('trail',):
            radius = max(5.0, p.size * 1.4)
        else:
            radius = max(4.0, p.size)
        # 加上更大的移动裕量，降低因位移/抗锯齿导致的未完全覆盖
        margin = 15  # 进一步增大到15像素，确保完全覆盖拖尾残留
        x = int(p.pos.x() - radius - margin)
        y = int(p.pos.y() - radius - margin)
        w = int(radius * 2 + margin * 2)
        h = int(radius * 2 + margin * 2)
        return QtCore.QRect(x, y, w, h)

    def paintEvent(self, ev: QtGui.QPaintEvent):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        
        # 强制清空整个重绘区域，使用最可靠的清除方式
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_Clear)
        painter.fillRect(self.rect(), QtCore.Qt.transparent)  # 清空整个窗口
        painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceOver)

        # 若当前不可见或无粒子，仅执行清理后返回
        if not self.visible_effects or not self.particles:
            painter.end()
            return

        # 性能优化：限制绘制的粒子数量
        max_draw_particles = 150 if self.performance_mode else 250
        particles_to_draw = self.particles[:min(len(self.particles), max_draw_particles)]

        for p in particles_to_draw:
            # 跳过透明度过低的粒子，避免绘制几乎看不见的残留
            if p.opacity < 0.05:
                continue
                
            if p.shape == 'text':
                painter.save()
                painter.translate(p.pos)
                painter.rotate(p.rotation)
                painter.setOpacity(p.opacity)
                font = painter.font()
                font.setPointSizeF(p.size)
                painter.setFont(font)
                painter.setPen(QtGui.QPen(p.color, 1))
                painter.drawText(QtCore.QPointF(0, 0), p.text)
                painter.restore()
            elif p.shape == 'star':
                painter.save()
                painter.translate(p.pos)
                painter.rotate(p.rotation)
                painter.setOpacity(p.opacity)
                painter.setBrush(p.color)
                painter.setPen(QtCore.Qt.NoPen)
                path = QtGui.QPainterPath()
                r = p.size
                for i in range(5):
                    angle = i * 72
                    angle2 = angle + 36
                    x1 = math.cos(math.radians(angle)) * r
                    y1 = math.sin(math.radians(angle)) * r
                    x2 = math.cos(math.radians(angle2)) * (r * 0.5)
                    y2 = math.sin(math.radians(angle2)) * (r * 0.5)
                    if i == 0:
                        path.moveTo(x1, y1)
                    else:
                        path.lineTo(x1, y1)
                    path.lineTo(x2, y2)
                path.closeSubpath()
                painter.drawPath(path)
                painter.restore()
            elif p.shape == 'circle':
                painter.save()
                painter.translate(p.pos)
                painter.setOpacity(p.opacity * 0.9)
                painter.setBrush(QtGui.QBrush(p.color.lighter(120)))
                painter.setPen(QtGui.QPen(p.color, 1))
                painter.drawEllipse(QtCore.QPointF(0, 0), p.size, p.size)
                painter.restore()
            elif p.shape == 'flower':
                painter.save()
                painter.translate(p.pos)
                painter.rotate(p.rotation)
                painter.setOpacity(p.opacity)
                petal_count = 5
                r = max(4.0, p.size * 0.6)
                petal_w = r * 0.9
                petal_h = r * 1.2
                base = QtGui.QColor(p.color)
                center_color = QtGui.QColor(base).lighter(120)
                for i in range(petal_count):
                    painter.save()
                    angle = i * (360.0 / petal_count)
                    painter.rotate(angle)
                    grad = QtGui.QRadialGradient(QtCore.QPointF(r * 0.2, 0), petal_h)
                    grad.setColorAt(0.0, base.lighter(150))
                    grad.setColorAt(1.0, base.darker(110))
                    painter.setBrush(QtGui.QBrush(grad))
                    painter.setPen(QtCore.Qt.NoPen)
                    rect = QtCore.QRectF(r * 0.2, -petal_w * 0.5, petal_h, petal_w)
                    painter.drawEllipse(rect)
                    painter.restore()
                painter.setBrush(center_color)
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(QtCore.QPointF(0, 0), r * 0.25, r * 0.25)
                painter.restore()
            elif p.shape == 'trail':
                painter.save()
                painter.translate(p.pos)
                painter.setOpacity(p.opacity)
                grad = QtGui.QRadialGradient(QtCore.QPointF(0, 0), p.size)
                c1 = QtGui.QColor(p.color)
                c1.setAlphaF(0.9 * p.opacity)
                c2 = QtGui.QColor(p.color)
                c2.setAlphaF(0.0)
                grad.setColorAt(0.0, c1)
                grad.setColorAt(1.0, c2)
                painter.setBrush(QtGui.QBrush(grad))
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(QtCore.QPointF(0, 0), p.size, p.size)
                painter.restore()
            elif p.shape == 'rect':
                painter.save()
                painter.translate(p.pos)
                painter.rotate(p.rotation)
                painter.setOpacity(p.opacity)
                painter.setBrush(p.color)
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawRect(-p.size * 0.4, -p.size * 0.1, p.size, p.size * 0.2)
                painter.restore()
        painter.end()
