# -*- coding: utf-8 -*-
"""NGS_Tools 主入口：主窗口与子功能窗口的启动器。"""

import sys
import webbrowser

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox

import requests

try:
    import qdarktheme
except ImportError:  # pyqtdarktheme 不支持 Python 3.12+，缺失时退回系统默认主题
    qdarktheme = None

from gui_NGS_Tools import Ui_MainWindow

import HDR_PE
import BE
import NHEJ
import bcl2fastq
import demultiplex

GITHUB_API_URL = "https://api.github.com/repos/sweety924/NGS_Tools/releases/latest"
GITHUB_RELEASE_URL = "https://github.com/sweety924/NGS_Tools/releases/latest"


class MyMainWin(QMainWindow, Ui_MainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.version = "1.7.0"
        self.setWindowTitle(self.windowTitle() + " v" + self.version)

        self.pushButton_bcl.clicked.connect(self.startBCL)
        self.pushButton_BE.clicked.connect(self.startBE)
        self.pushButton_HDR.clicked.connect(self.startHDR)
        self.pushButton_NHEJ.clicked.connect(self.startNHEJ)
        self.pushButton_demultiplex.clicked.connect(self.startDemultiplex)

        self.centerWin()
        # 检查更新放到窗口显示后再异步进行，避免阻塞启动。
        QtCore.QTimer.singleShot(0, self.checkUpdate)

    def checkUpdate(self):
        """使用 GitHub API 检查最新版本。"""
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.0.0 Safari/537.36"
            )
        }
        try:
            response = requests.get(GITHUB_API_URL, timeout=1.5, headers=headers)
            info = response.json()
            # GitHub 的 tag 常带 "v" 前缀，如 "v1.7.0"，这里统一去掉再比较。
            latest_version = str(info.get("tag_name", "")).lstrip("v")
            release_info = info.get("body", "")
            print("Current Version:", self.version)
            print("Latest Version:", latest_version)

            if not latest_version or latest_version == self.version:
                return

            msg = latest_version + "\n" + release_info
            answer = QMessageBox.question(
                self,
                "New version",
                "----------------|有新版本啦\t  ε٩(๑> ₃ <)۶з |----------------\n\n\n"
                + msg
                + "请下载最新版本，解压后在属性中赋予运行权限再使用\n\n 现在更新?",
            )
            if answer == QMessageBox.Yes:
                webbrowser.open(GITHUB_RELEASE_URL)
                QMessageBox.about(
                    self,
                    "Stopped",
                    "请下载最新版本使用。\n解压最新版本后，在属性中赋予运行权限再使用。",
                )
        except Exception as e:  # noqa: BLE001 - 网络异常时静默跳过更新检查
            print(e)

    def centerWin(self):
        """让窗体在主屏幕居中显示。"""
        center = QApplication.primaryScreen().availableGeometry().center()
        self.frameGeometry().moveCenter(center)
        self.move(self.pos())

    def startBCL(self):
        self.subwin_bcl = bcl2fastq.MyMainWin()
        self.subwin_bcl.show()

    def startDemultiplex(self):
        self.subwin_d = demultiplex.MyMainWin()
        self.subwin_d.show()

    def startHDR(self):
        self.subwin_hdr = HDR_PE.MyMainWin()
        self.subwin_hdr.show()

    def startBE(self):
        self.subwin_be = BE.MyMainWin()
        self.subwin_be.show()

    def startNHEJ(self):
        self.subwin_nhej = NHEJ.MyMainWin()
        self.subwin_nhej.show()


if __name__ == "__main__":
    # 开启 HiDPI 缩放（pyqtdarktheme 2.x 已移除 enable_hi_dpi()，改用 Qt 原生属性）
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps)
    app = QApplication(sys.argv)
    if qdarktheme is not None:
        qdarktheme.setup_theme("dark")
    win = MyMainWin()
    win.show()
    sys.exit(app.exec_())
