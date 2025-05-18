import sys
import os
import requests
import zipfile
import shutil
import sqlite3
import bcrypt
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QMessageBox
from customized import PasswordEdit
import icons_rc  # Needed for resource icons

GITHUB_REPO = "yourusername/yourrepo"
APP_NAME = "main.app"  # or main.exe on Windows
DOWNLOAD_NAME = "main.zip"  # The name of the asset in your GitHub release

DB_FILE = "users.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_user(username, password):
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
    conn.commit()
    conn.close()

def verify_user(username, password):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT password_hash FROM users WHERE username=?", (username,))
    row = c.fetchone()
    conn.close()
    if row:
        return bcrypt.checkpw(password.encode(), row[0])
    return False

def get_latest_release_info():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    return resp.json()

def download_latest_release(asset_url, dest_path):
    resp = requests.get(asset_url, stream=True)
    resp.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

def extract_zip(zip_path, extract_to):
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)

class ModernLoginForm(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        self.resize(420, 540)
        self.setMinimumSize(380, 480)
        self.setMaximumSize(500, 650)
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint)
        self.setStyleSheet("""
            QPushButton {
                border-style: outset;
                border-radius: 0px;
                padding: 6px;
            }
            QPushButton:hover {
                background-color: #cf7500;
                border-style: inset;
            }
            QPushButton:pressed {
                background-color: #ffa126;
                border-style: inset;
            }
        """)

        self.verticalLayout = QtWidgets.QVBoxLayout(self)
        self.verticalLayout.setContentsMargins(0, 0, 0, 0)
        self.verticalLayout.setSpacing(0)

        self.horizontalLayout_3 = QtWidgets.QHBoxLayout()
        self.horizontalLayout_3.setContentsMargins(0, 0, 0, 0)

        self.widget = QtWidgets.QWidget(self)
        self.widget.setMaximumSize(QtCore.QSize(16777215, 16777215))
        self.widget.setStyleSheet(".QWidget{background-color: rgb(20, 20, 40);}")

        self.verticalLayout_2 = QtWidgets.QVBoxLayout(self.widget)
        self.verticalLayout_2.setContentsMargins(9, 0, 9, 0)
        self.verticalLayout_2.setSpacing(0)

        self.pushButton_3 = QtWidgets.QPushButton(self.widget)
        self.pushButton_3.setFixedSize(35, 25)
        self.pushButton_3.setStyleSheet("color: white; font: 13pt \"Verdana\"; border-radius: 1px; opacity: 200;")
        self.pushButton_3.setText("X")
        self.pushButton_3.clicked.connect(self.close)
        self.verticalLayout_2.addWidget(self.pushButton_3, 0, QtCore.Qt.AlignRight)

        self.verticalLayout_3 = QtWidgets.QVBoxLayout()
        self.verticalLayout_3.setContentsMargins(-1, 10, -1, -1)
        self.verticalLayout_3.setSpacing(10)

        self.label = QtWidgets.QLabel(self.widget)
        self.label.setFixedSize(100, 100)
        self.label.setStyleSheet("image: url(:/icons/icons/rocket_48x48.png);")
        self.verticalLayout_3.addWidget(self.label, 0, QtCore.Qt.AlignHCenter)

        self.formLayout_2 = QtWidgets.QFormLayout()
        self.formLayout_2.setContentsMargins(30, 20, 30, 10)
        self.formLayout_2.setSpacing(15)

        self.label_2 = QtWidgets.QLabel(self.widget)
        self.label_2.setStyleSheet("color: rgb(231, 231, 231); font: 15pt \"Verdana\";")
        self.label_2.setText('<img src=":/icons/icons/user_32x32.png"/>')
        self.formLayout_2.setWidget(0, QtWidgets.QFormLayout.LabelRole, self.label_2)

        self.lineEdit = QtWidgets.QLineEdit(self.widget)
        self.lineEdit.setMinimumHeight(36)
        self.lineEdit.setStyleSheet("""
            QLineEdit {
                color: rgb(231, 231, 231);
                font: 15pt "Verdana";
                border: None;
                border-bottom: 1px solid #ffa126;
                border-radius: 10px;
                padding: 0 8px;
                background: rgb(20, 20, 40);
                selection-background-color: darkgray;
            }
        """)
        self.lineEdit.setPlaceholderText("Username")
        self.formLayout_2.setWidget(0, QtWidgets.QFormLayout.FieldRole, self.lineEdit)

        self.label_3 = QtWidgets.QLabel(self.widget)
        self.label_3.setText('<img src=":/icons/icons/lock_or_32x32.png"/>')
        self.formLayout_2.setWidget(2, QtWidgets.QFormLayout.LabelRole, self.label_3)

        self.lineEdit_2 = PasswordEdit(self.widget)
        self.lineEdit_2.setMinimumHeight(36)
        self.lineEdit_2.setStyleSheet("""
            QLineEdit {
                color: orange;
                font: 15pt "Verdana";
                border: None;
                border-bottom: 1px solid #ffa126;
                border-radius: 10px;
                padding: 0 8px;
                background: rgb(20, 20, 40);
                selection-background-color: darkgray;
            }
        """)
        self.lineEdit_2.setPlaceholderText("Password")
        self.formLayout_2.setWidget(2, QtWidgets.QFormLayout.FieldRole, self.lineEdit_2)

        self.pushButton = QtWidgets.QPushButton(self.widget)
        self.pushButton.setMinimumHeight(48)
        self.pushButton.setStyleSheet("""
            color: rgb(231, 231, 231);
            font: 17pt "Verdana";
            border: 2px solid orange;
            padding: 5px;
            border-radius: 3px;
            opacity: 200;
        """)
        self.pushButton.setText("Sign In")
        self.pushButton.clicked.connect(self.handle_login)
        self.formLayout_2.setWidget(7, QtWidgets.QFormLayout.SpanningRole, self.pushButton)

        self.verticalLayout_3.addLayout(self.formLayout_2)
        self.verticalLayout_2.addLayout(self.verticalLayout_3)
        self.verticalLayout_2.addStretch(1)
        self.horizontalLayout_3.addWidget(self.widget)
        self.verticalLayout.addLayout(self.horizontalLayout_3)

    # ... rest of your class unchanged ...

    def handle_login(self):
        user = self.lineEdit.text().strip()
        pw = self.lineEdit_2.text()
        if not user or not pw:
            QMessageBox.warning(self, "Login Failed", "Please enter both username and password.")
            return
        if verify_user(user, pw):
            self.pushButton.setEnabled(False)
            self.pushButton.setText("Checking for updates...")
            QtWidgets.QApplication.processEvents()
            try:
                self.check_and_update()
                self.launch_main_app()
                self.close()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))
                self.pushButton.setEnabled(True)
                self.pushButton.setText("Sign In")
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid credentials.")

    def check_and_update(self):
        info = get_latest_release_info()
        latest_version = info["tag_name"]
        version_file = "current_version.txt"
        current_version = None
        if os.path.exists(version_file):
            with open(version_file, "r") as f:
                current_version = f.read().strip()
        if current_version != latest_version:
            asset = next((a for a in info["assets"] if a["name"] == DOWNLOAD_NAME), None)
            if not asset:
                raise Exception("Release asset not found.")
            download_latest_release(asset["browser_download_url"], DOWNLOAD_NAME)
            if os.path.exists(APP_NAME):
                if os.path.isdir(APP_NAME):
                    shutil.rmtree(APP_NAME)
                else:
                    os.remove(APP_NAME)
            extract_zip(DOWNLOAD_NAME, ".")
            os.remove(DOWNLOAD_NAME)
            with open(version_file, "w") as f:
                f.write(latest_version)

    def launch_main_app(self):
        if sys.platform == "darwin":
            os.system(f"open ./{APP_NAME}")
        elif sys.platform == "win32":
            os.startfile(APP_NAME)
        else:
            os.system(f"./{APP_NAME} &")

if __name__ == "__main__":
    init_db()
    # Add test user (run once, then comment this line for security)
    add_user("admin1", "admin1")
    app = QtWidgets.QApplication(sys.argv)
    login_form = ModernLoginForm()
    login_form.show()
    sys.exit(app.exec_())