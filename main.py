import os
import sys
import tempfile
import psutil
import requests
import time
import threading
import random
import multiprocessing
import undetected_chromedriver as uc
from selenium.webdriver.chrome.options import Options
from queue import Queue
from PyQt5.QtWidgets import (
    QApplication, QWidget, QPushButton, QProgressBar, QVBoxLayout, QHBoxLayout,
    QListWidget, QListWidgetItem, QLabel, QStackedLayout, QMessageBox,
    QGraphicsView, QGraphicsScene, QGraphicsEllipseItem, QFrame
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QTimer
from PyQt5.QtGui import QFont, QColor, QBrush, QPainter
import ssl
import certifi
from PyQt5.QtNetwork import QLocalServer, QLocalSocket

ssl._create_default_https_context = lambda: ssl.create_default_context(cafile=certifi.where())

def resource_path(filename):
    """Get absolute path to resource, works for dev and for PyInstaller bundle."""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, filename)
    return os.path.abspath(filename)

def get_onedrive_path():
    home = os.path.expanduser("~")
    possible = [
        os.path.join(home, "OneDrive"),
        os.path.join(home, "OneDrive - Personal"),
        os.path.join(home, "OneDrive - " + os.environ.get("USER", "")),
    ]
    for path in possible:
        if os.path.exists(path):
            return path
    return None

API_KEY = "s917muk5z8voh6c0ik7z"
PROXIES_API_URL = (
    "https://api.proxyscrape.com/v2/?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all"
    f"&key={API_KEY}"
)
PROXYINFO_API_URL = "https://api.proxyscrape.com/v2/?request=proxyinfo"
CACHE_FILE = os.path.join(os.path.expanduser("~"), "working_proxies_cache.txt")
MAX_WORKING_PROXIES = 100
THREAD_COUNT = 20

def debug_log(msg):
    print(f"[DEBUG][PID {os.getpid()}] {msg}")

def ensure_single_instance():
    tmpdir = tempfile.gettempdir()
    lockfile = os.path.join(tmpdir, "LMVPN_single_instance.lock")
    current_pid = os.getpid()
    if os.path.exists(lockfile):
        try:
            with open(lockfile, "r") as f:
                old_pid = int(f.read().strip())
            if old_pid != current_pid and psutil.pid_exists(old_pid):
                debug_log(f"Another instance detected (PID {old_pid}). Exiting this instance.")
                sys.exit(0)
        except Exception as e:
            pass
    with open(lockfile, "w") as f:
        f.write(str(current_pid))
    return lockfile

def is_another_instance_running(app_id="LMVPN_SINGLE_INSTANCE"):
    socket = QLocalSocket()
    socket.connectToServer(app_id)
    if socket.waitForConnected(100):
        socket.close()
        return True
    socket.close()
    global _single_instance_server
    _single_instance_server = QLocalServer()
    _single_instance_server.listen(app_id)
    return False

def country_code_to_emoji(code):
    if not code or len(code) != 2:
        return "🌐"
    return chr(ord(code[0].upper()) + 127397) + chr(ord(code[1].upper()) + 127397)

def load_cached_proxies():
    try:
        with open(CACHE_FILE, "r") as f:
            lines = f.read().splitlines()
            proxies = []
            for line in lines:
                parts = line.split(",")
                if len(parts) == 4:
                    proxy, emoji, country, speed_ms = parts
                    proxies.append((proxy, emoji, country, int(speed_ms)))
            return proxies
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"Error loading cached proxies: {e}")
        return []

def save_cached_proxies(proxies):
    try:
        with open(CACHE_FILE, "w") as f:
            for proxy, emoji, country, speed_ms in proxies:
                f.write(f"{proxy},{emoji},{country},{speed_ms}\n")
    except Exception as e:
        print(f"Error saving cached proxies: {e}")

class ParticleView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background: transparent;")
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setRenderHint(QPainter.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFrameStyle(0)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.particles = []
        self.timer = QTimer()
        self.timer.timeout.connect(self.animate_particles)
        self.timer.start(40)
        self.init_particles(35)

    def resizeEvent(self, event):
        self.setSceneRect(0, 0, self.width(), self.height())

    def init_particles(self, count):
        for _ in range(count):
            size = random.randint(2, 6)
            x = random.uniform(0, self.width())
            y = random.uniform(0, self.height())
            dx = random.uniform(-0.6, 0.6)
            dy = random.uniform(-0.6, 0.6)
            color = QColor(255, 255, 255, 50)
            item = QGraphicsEllipseItem(0, 0, size, size)
            item.setBrush(QBrush(color))
            item.setPos(x, y)
            self.scene.addItem(item)
            self.particles.append((item, dx, dy))

    def animate_particles(self):
        for idx, (item, dx, dy) in enumerate(self.particles):
            pos = item.pos()
            new_x = pos.x() + dx
            new_y = pos.y() + dy
            if new_x < 0 or new_x > self.width():
                dx *= -1
            if new_y < 0 or new_y > self.height():
                dy *= -1
            self.particles[idx] = (item, dx, dy)
            item.setPos(new_x, new_y)

class ProxyFetchThread(QThread):
    proxy_checked = pyqtSignal(tuple)
    error_occurred = pyqtSignal(str)
    progress_updated = pyqtSignal(int)
    finished_checking = pyqtSignal()

    def __init__(self, use_only_cache=False):
        super().__init__()
        self.use_only_cache = use_only_cache

    def run(self):
        try:
            cached_proxies = load_cached_proxies()
            if self.use_only_cache:
                if cached_proxies:
                    for proxy, emoji, country, speed_ms in cached_proxies[:MAX_WORKING_PROXIES]:
                        self.proxy_checked.emit((proxy, emoji, country, speed_ms, True))
                    self.progress_updated.emit(100)
                    self.finished_checking.emit()
                else:
                    self.error_occurred.emit("No cached proxies available.")
                return

            try:
                resp = requests.get(PROXIES_API_URL, timeout=12, verify=False)
                resp.raise_for_status()
                proxies_text = resp.text.strip()
                if not proxies_text:
                    self.error_occurred.emit("No proxies returned from API.")
                    return
                all_proxies = proxies_text.splitlines()[:MAX_WORKING_PROXIES]
            except Exception as e:
                self.error_occurred.emit(f"Failed to fetch proxies: {e}")
                return

            results = []
            checked = 0
            lock = threading.Lock()
            q = Queue()
            for proxy in all_proxies:
                q.put(proxy)

            def worker():
                nonlocal checked
                while not q.empty():
                    try:
                        proxy = q.get()
                        start = time.time()
                        is_working = False
                        emoji = "🌐"
                        country = "N/A"
                        speed_ms = 9999
                        try:
                            r = requests.get(
                                "https://httpbin.org/ip",
                                proxies={"http": f"http://{proxy}", "https": f"http://{proxy}"},
                                timeout=5,
                                verify=False
                            )
                            elapsed_ms = int((time.time() - start) * 1000)
                            if r.status_code == 200:
                                is_working = True
                                speed_ms = elapsed_ms
                                try:
                                    info_resp = requests.get(
                                        f"{PROXYINFO_API_URL}&proxy={proxy}&key={API_KEY}", timeout=6, verify=False
                                    )
                                    info_resp.raise_for_status()
                                    info_json = info_resp.json()
                                    country = info_json.get("country", "")
                                    emoji = country_code_to_emoji(country)
                                except Exception:
                                    country = "N/A"
                                    emoji = "🌐"
                        except Exception:
                            pass

                        with lock:
                            results.append((proxy, emoji, country or "N/A", speed_ms, is_working))
                            checked += 1
                            self.proxy_checked.emit((proxy, emoji, country or "N/A", speed_ms, is_working))
                            progress = int(checked / len(all_proxies) * 100)
                            self.progress_updated.emit(progress)
                        q.task_done()
                    except Exception as e:
                        import traceback
                        self.error_occurred.emit(f"Worker crashed: {e}\n{traceback.format_exc()}")
                        q.task_done()

            threads = []
            for _ in range(min(THREAD_COUNT, q.qsize())):
                t = threading.Thread(target=worker)
                t.daemon = True
                t.start()
                threads.append(t)

            q.join()
            self.progress_updated.emit(100)
            working_proxies = [p[:4] for p in results if p[4]]
            if working_proxies:
                save_cached_proxies(working_proxies)
            self.finished_checking.emit()
        except Exception as e:
            import traceback
            self.error_occurred.emit(f"Thread crashed: {e}\n{traceback.format_exc()}")

class AnimatedSidebar(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(60)
        self.setStyleSheet("background-color: #222222; border-right: 2px solid #444444;")
        self.setMouseTracking(True)
        self.animation = QPropertyAnimation(self, b"minimumWidth")
        self.animation.setDuration(400)
        self.animation.setEasingCurve(QEasingCurve.InOutCubic)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(10, 10, 10, 10)
        self.layout.setSpacing(20)

        self.btn_home = QPushButton("🏠 Home")
        self.btn_proxy = QPushButton("🌍 Proxy")
        self.btn_settings = QPushButton("🛠️ BugFix")

        for btn in (self.btn_home, self.btn_proxy, self.btn_settings):
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet("""
                QPushButton {
                    color: #ccc;
                    background: transparent;
                    border: none;
                    text-align: left;
                    padding-left: 15px;
                    font-size: 18px;
                }
                QPushButton:hover {
                    color: #e74c3c;
                }
                QPushButton:pressed {
                    color: #c0392b;
                }
            """)
            btn.setFixedHeight(40)
            self.layout.addWidget(btn)
        self.layout.addStretch()

    def enterEvent(self, event):
        self.animation.stop()
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(200)
        self.animation.start()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.animation.stop()
        self.animation.setStartValue(self.width())
        self.animation.setEndValue(60)
        self.animation.start()
        super().leaveEvent(event)

class ProxySelectPage(QWidget):
    def __init__(self, on_proxy_selected):
        super().__init__()
        self.on_proxy_selected = on_proxy_selected
        self.use_cache_only = True
        self.proxies = []
        self.thread = None
        self.init_ui()
        self.load_proxies(use_only_cache=True)

    def init_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        title = QLabel("🌍 Select Proxy Server")
        title.setFont(QFont("Segoe UI", 22, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: #e74c3c;")
        main_layout.addWidget(title)

        self.list_widget = QListWidget()
        self.list_widget.setStyleSheet("""
            QListWidget {
                background-color: #1e1e1e;
                border: 2px solid #e74c3c;
                border-radius: 12px;
                color: white;
                font-size: 14pt;
            }
            QListWidget::item:selected {
                background-color: #c0392b;
                color: white;
                border-radius: 8px;
            }
        """)
        self.list_widget.itemSelectionChanged.connect(self.proxy_selected)
        main_layout.addWidget(self.list_widget)

        self.status_label = QLabel("Loading proxies...")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFont(QFont("Segoe UI", 11))
        self.status_label.setStyleSheet("color: #ecf0f1;")
        main_layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #c0392b;
                border-radius: 10px;
                text-align: center;
                color: white;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: #e74c3c;
                border-radius: 8px;
            }
        """)
        main_layout.addWidget(self.progress_bar)

        btn_layout = QHBoxLayout()
        self.cache_toggle = QPushButton("Use Cached Proxies ✅")
        self.cache_toggle.setCheckable(True)
        self.cache_toggle.setChecked(True)
        self.cache_toggle.clicked.connect(self.toggle_cache_mode)
        self.cache_toggle.setStyleSheet("""
            QPushButton {
                background-color: #34495e;
                color: white;
                border-radius: 10px;
                padding: 8px 15px;
            }
            QPushButton:checked {
                background-color: #e74c3c;
            }
        """)
        btn_layout.addWidget(self.cache_toggle)

        self.refresh_btn = QPushButton("Refresh List 🔄")
        self.refresh_btn.setFont(QFont("Segoe UI", 11, QFont.Bold))
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 15px;
                padding: 10px 25px;
            }
            QPushButton:hover {
                background-color: #ff7675;
            }
            QPushButton:pressed {
                background-color: #c0392b;
            }
        """)
        self.refresh_btn.clicked.connect(lambda: self.load_proxies(use_only_cache=False))
        btn_layout.addWidget(self.refresh_btn)

        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

    def toggle_cache_mode(self):
        self.use_cache_only = self.cache_toggle.isChecked()
        label = "Use Cached Proxies ✅" if self.use_cache_only else "Use Cached Proxies ❌"
        self.cache_toggle.setText(label)

    def load_proxies(self, use_only_cache=None):
        if use_only_cache is not None:
            self.use_cache_only = use_only_cache

        self.status_label.setText("Loading proxies...")
        self.list_widget.clear()
        self.proxies = []
        self.progress_bar.setValue(0)
        self.refresh_btn.setEnabled(False)
        self.cache_toggle.setEnabled(False)

        if self.thread is not None and self.thread.isRunning():
            self.status_label.setText("Please wait for the current check to finish.")
            return

        self.thread = ProxyFetchThread(use_only_cache=self.use_cache_only)
        self.thread.proxy_checked.connect(self.on_proxy_checked)
        self.thread.error_occurred.connect(self.on_error)
        self.thread.progress_updated.connect(self.progress_bar.setValue)
        self.thread.finished_checking.connect(self.on_finished_checking)
        self.thread.start()

    def on_proxy_checked(self, proxy_tuple):
        try:
            proxy, emoji, country, speed_ms, is_working = proxy_tuple
            self.proxies = [p for p in self.proxies if p[0] != proxy]
            self.proxies.append(proxy_tuple)
            self.proxies.sort(key=lambda x: (not x[4], x[3]))
            self.update_list_widget()
        except Exception as e:
            print(f"Error in on_proxy_checked: {e}")

    def update_list_widget(self):
        try:
            self.list_widget.clear()
            for proxy, emoji, country, speed_ms, is_working in self.proxies:
                mark = "✅" if is_working else "❌"
                item_text = f"{mark} {emoji} {proxy} ({country}) - {speed_ms} ms"
                item = QListWidgetItem(item_text)
                item.setData(Qt.UserRole, proxy if is_working else None)
                self.list_widget.addItem(item)
            self.status_label.setText(f"Checked {len(self.proxies)} proxies.")
        except Exception as e:
            print(f"Error in update_list_widget: {e}")

    def on_finished_checking(self):
        try:
            self.refresh_btn.setEnabled(True)
            self.cache_toggle.setEnabled(True)
            self.progress_bar.setValue(100)
            self.status_label.setText(f"Done. {sum(1 for p in self.proxies if p[4])} working proxies found.")
        except Exception as e:
            print(f"Error in on_finished_checking: {e}")

    def on_error(self, msg):
        try:
            print(msg)
            self.status_label.setText(f"Error: {msg}")
            self.refresh_btn.setEnabled(True)
            self.cache_toggle.setEnabled(True)
            self.progress_bar.setValue(0)
        except Exception as e:
            print(f"Error in on_error: {e}")

    def proxy_selected(self):
        try:
            selected_items = self.list_widget.selectedItems()
            if selected_items:
                idx = self.list_widget.row(selected_items[0])
                proxy_tuple = self.proxies[idx]
                if proxy_tuple[4]:
                    self.on_proxy_selected(proxy_tuple[0])
        except Exception as e:
            print(f"Error in proxy_selected: {e}")

class HomePage(QWidget):
    def __init__(self, get_selected_proxy):
        super().__init__()
        self.get_selected_proxy = get_selected_proxy
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(25)

        self.info_label = QLabel("")
        self.info_label.setFont(QFont("Segoe UI", 14))
        self.info_label.setAlignment(Qt.AlignCenter)
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("color: #ecf0f1;")
        layout.addWidget(self.info_label)

        self.button = QPushButton('🚀 Launch VPN Browser')
        self.button.setFont(QFont('Segoe UI', 20, QFont.Bold))
        self.button.setStyleSheet(
            """
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 25px;
                padding: 20px;
                box-shadow: 2px 2px 10px rgba(0,0,0,0.3);
            }
            QPushButton:hover {
                background-color: #ff7675;
            }
            QPushButton:pressed {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #7f8c8d;
                color: #bdc3c7;
            }
            """
        )
        self.button.setFixedHeight(70)
        self.button.clicked.connect(self.prepare_launch)
        layout.addWidget(self.button)

        self.loading_bar = QProgressBar()
        self.loading_bar.setVisible(False)
        self.loading_bar.setRange(0, 100)
        self.loading_bar.setTextVisible(True)
        self.loading_bar.setStyleSheet("""
            QProgressBar {
                border: 2px solid #c0392b;
                border-radius: 15px;
                text-align: center;
                color: white;
                font-weight: bold;
                height: 30px;
            }
            QProgressBar::chunk {
                background-color: #e74c3c;
                border-radius: 13px;
            }
        """)
        layout.addWidget(self.loading_bar)

        self.setLayout(layout)

    def update_proxy_info(self, proxy):
        if proxy:
            self.info_label.setText(f"Selected Proxy:\n{proxy}")
            self.button.setEnabled(True)
        else:
            self.info_label.setText("No proxy selected. Please select a proxy.")
            self.button.setEnabled(False)

    def prepare_launch(self):
        proxy_url = self.get_selected_proxy()
        if not proxy_url:
            QMessageBox.warning(self, "No Proxy Selected", "Please select a proxy first!")
            return

        self.button.setEnabled(False)
        self.loading_bar.setVisible(True)
        self.loading_bar.setValue(0)

        self.anim = QPropertyAnimation(self.loading_bar, b"value")
        self.anim.setDuration(3000)
        self.anim.setStartValue(0)
        self.anim.setEndValue(100)
        self.anim.setEasingCurve(QEasingCurve.InOutCubic)
        self.anim.finished.connect(lambda: self.launch_chrome(proxy_url))
        self.anim.start()

    def launch_chrome(self, proxy_url):
        try:
            options = uc.ChromeOptions()
            options.add_argument("--no-first-run")
            options.add_argument("--no-default-browser-check")
            options.add_argument("--disable-blink-features=AutomationControlled")
            options.add_argument("--disable-infobars")
            options.add_argument("--incognito")
            options.add_argument(f"--proxy-server=http://{proxy_url}")
            options.add_argument("--user-data-dir=/tmp/fresh_chrome_profile")
            options.add_argument("--start-maximized")
            options.add_argument("--ignore-certificate-errors")

            driver = uc.Chrome(options=options)

        except Exception as e:
            QMessageBox.critical(self, "Launch Failed", f"Failed to launch Chrome:\n{e}")
        finally:
            self.loading_bar.setVisible(False)
            self.button.setEnabled(True)

class SettingsPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()
        label = QLabel("BugFix and About")
        label.setFont(QFont("Segoe UI", 18, QFont.Bold))
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #ecf0f1;")
        layout.addWidget(label)

        info = QLabel("This is a VPN Unblocker.\nDeveloped By Lior.\nIf the app fully stops working let me know.")
        info.setFont(QFont("Segoe UI", 12))
        info.setAlignment(Qt.AlignCenter)
        info.setStyleSheet("color: #ccc;")
        layout.addWidget(info)
        layout.addStretch()

        self.setLayout(layout)

class VPNLauncher(QWidget):
    def __init__(self):
        super().__init__()
        self.selected_proxy = None
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("Lior's VPN Chrome Launcher")
        self.resize(900, 600)
        self.setStyleSheet("""
            background-color: #121212;
            color: white;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        """)

        self.particles = ParticleView(self)
        self.particles.setGeometry(0, 0, self.width(), self.height())
        self.particles.lower()

        self.sidebar = AnimatedSidebar()
        self.sidebar.btn_home.clicked.connect(lambda: self.stack.setCurrentWidget(self.home_page))
        self.sidebar.btn_proxy.clicked.connect(lambda: self.stack.setCurrentWidget(self.proxy_select_page))
        self.sidebar.btn_settings.clicked.connect(lambda: self.stack.setCurrentWidget(self.settings_page))

        self.stack = QStackedLayout()
        self.home_page = HomePage(self.get_selected_proxy)
        self.proxy_select_page = ProxySelectPage(self.on_proxy_selected)
        self.settings_page = SettingsPage()
        self.stack.addWidget(self.home_page)
        self.stack.addWidget(self.proxy_select_page)
        self.stack.addWidget(self.settings_page)

        main_layout = QHBoxLayout()
        main_layout.addWidget(self.sidebar)
        main_layout.addLayout(self.stack)
        self.setLayout(main_layout)

        self.stack.setCurrentWidget(self.proxy_select_page)
        self.resizeEvent = self.on_resize

    def on_resize(self, event):
        self.particles.setGeometry(0, 0, self.width(), self.height())
        event.accept()

    def on_proxy_selected(self, proxy):
        self.selected_proxy = proxy
        self.home_page.update_proxy_info(proxy)
        self.stack.setCurrentWidget(self.home_page)

    def get_selected_proxy(self):
        return self.selected_proxy

if __name__ == "__main__":
    multiprocessing.freeze_support()
    if is_another_instance_running():
        debug_log("Another instance detected. Exiting.")
        sys.exit(0)
    debug_log("Entered __main__ block.")
    app = QApplication(sys.argv)
    debug_log("Created QApplication.")
    window = VPNLauncher()
    debug_log("Created VPNLauncher window.")
    window.show()
    debug_log("Window shown. Entering app.exec_() loop.")
    sys.exit(app.exec_())