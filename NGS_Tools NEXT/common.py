# -*- coding: utf-8 -*-
"""NGS_Tools 公共工具模块。

集中存放被各 GUI 模块重复实现的工具函数与表格操作方法，避免代码重复，
并统一管理 conda / 环境等配置项。

所有 GUI 窗口通过继承 :class:`TableWindowMixin` 获得通用表格与文件选择能力；
``reverseDNA`` / ``getLyric`` 等函数也从本模块导入，不再在每个模块中复制粘贴。
"""

import json
import os
import shlex
import subprocess
from urllib.parse import unquote

from PyQt5.QtCore import QThread, QUrl, pyqtSignal
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtWidgets import QFileDialog, QHBoxLayout, QLabel, QSpinBox, QTableWidgetItem

import requests

# ---------------------------------------------------------------------------
# 全局配置
# ---------------------------------------------------------------------------

# conda 安装目录（相对家目录）与 conda 环境名，集中管理，避免散落在各处。
CONDA_DIR = "~/miniconda3"
CONDA_ENV = "NGS"

# conda 可执行文件绝对路径。
CONDA_EXE = os.path.expanduser(os.path.join(CONDA_DIR, "bin", "conda"))

# NGS 环境目录及其 bin 目录（用于直接调用环境内的可执行文件，绕过 conda run）。
CONDA_ENV_DIR = os.path.expanduser(os.path.join(CONDA_DIR, "envs", CONDA_ENV))
CONDA_ENV_BIN = os.path.join(CONDA_ENV_DIR, "bin")


def _env_int(name, default):
    """从环境变量读取整数，失败时返回默认值。"""
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# 用户配置持久化（~/.NGS_Tools/config.json）
# ---------------------------------------------------------------------------

CONFIG_PATH = os.path.expanduser("~/.NGS_Tools/config.json")
_config_cache = None


def _load_config():
    global _config_cache
    if _config_cache is None:
        try:
            with open(CONFIG_PATH) as f:
                _config_cache = json.load(f)
        except Exception:
            _config_cache = {}
    return _config_cache


def get_config(key, default=None):
    """读取用户配置项。"""
    return _load_config().get(key, default)


def set_config(key, value):
    """写入用户配置项（并持久化到磁盘）。"""
    data = _load_config()
    data[key] = value
    try:
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:  # noqa: BLE001
        print("保存配置失败:", e)


def default_parallel():
    """外层并发样本数默认值。

    优先级：上次保存的配置 > 环境变量 ``NGS_MAX_PARALLEL`` > ``min(CPU核数, 8)``。
    每个 CRISPResso 进程本身占 1~4GB 内存，并发过高容易 OOM。
    """
    saved = get_config("parallel")
    if saved is not None:
        try:
            return max(1, int(saved))
        except (TypeError, ValueError):
            pass
    return max(1, _env_int("NGS_MAX_PARALLEL", min(int(os.cpu_count() or 1), 8)))


def default_processes():
    """每个 CRISPResso 进程内部线程数（-p）默认值。

    优先级：上次保存的配置 > 环境变量 ``NGS_CRISPRESSO_PROCESSES`` > 3。
    """
    saved = get_config("crispresso_processes")
    if saved is not None:
        try:
            return max(1, int(saved))
        except (TypeError, ValueError):
            pass
    return max(1, _env_int("NGS_CRISPRESSO_PROCESSES", 3))


def process_arg(n):
    """根据内层线程数返回追加到 CRISPResso 命令的 ``-p N`` 参数（<=1 返回空串）。"""
    n = int(n)
    return "" if n <= 1 else " -p %d" % n


def conda_run_args(*args):
    """构造 ``conda run -n <env> <args...>`` 的参数列表（用于 subprocess）。"""
    return [CONDA_EXE, "run", "-n", CONDA_ENV, *args]


def bash_header():
    """生成批处理脚本头部，激活 conda 环境。"""
    return "#!/bin/bash\nsource %s/bin/activate %s\n" % (CONDA_DIR, CONDA_ENV)


# ---------------------------------------------------------------------------
# 「今日诗词」彩蛋（可开关）
# ---------------------------------------------------------------------------
# 通过环境变量 ``NGS_TOOLS_LYRIC`` 控制：设为 ``0`` / ``off`` / ``false`` 关闭。
_STATIC_LYRIC = "扩增子测序分析" + "\n\t\t\t" + "——Written by M.Q. at ShanghaiTech University"


def lyric_enabled():
    """判断「今日诗词」彩蛋是否开启（默认开启）。"""
    value = os.environ.get("NGS_TOOLS_LYRIC", "1")
    return value.lower() not in ("0", "false", "no", "off")


def getLyric():
    """获取展示在标签栏的文案。

    开启时尝试从 jinrishici.com 拉取一句诗词；关闭或网络失败时返回兜底文案。
    """
    if not lyric_enabled():
        return _STATIC_LYRIC
    try:
        url = "https://v1.jinrishici.com/all"
        lyric = requests.get(url, timeout=1).json()
        content = lyric["content"]
        origin = lyric.get("origin", "Unknown")
        author = lyric.get("author", "Unknown")
        return content + "\n\t\t\t" + "——《" + origin + "》\t" + author
    except Exception as e:  # noqa: BLE001 - 网络请求失败时静默降级
        print(e)
        return _STATIC_LYRIC


# ---------------------------------------------------------------------------
# DNA 序列工具
# ---------------------------------------------------------------------------

def reverseDNA(dna):
    """求 DNA 序列的反向互补序列（非 A/T/C/G 记为 N）。"""
    complement = {"A": "T", "T": "A", "C": "G", "G": "C"}
    dna = dna.upper().strip()
    return "".join(complement.get(base, "N") for base in reversed(dna))


# ---------------------------------------------------------------------------
# 环境探测
# ---------------------------------------------------------------------------

def _run_conda_full(args, timeout=60):
    """运行 ``conda run -n <env> <args...>`` 并返回 ``(返回码, stdout, stderr)``。"""
    proc = subprocess.run(
        conda_run_args(*args),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def detect_bcl2fastq():
    """探测 bcl2fastq 是否已安装，返回 ``(是否就绪, 版本标签)``。"""
    _, stdout, stderr = _run_conda_full(["bcl2fastq", "-v"])
    out = stdout + stderr
    ok = "Illumina" in out
    return ok, (out.strip() if ok else "未安装")


def detect_crispresso():
    """探测 CRISPResso2 是否已安装，返回 ``(是否就绪, 版本标签)``。

    用 ``--help`` 的返回码判断（argparse 一定支持 --help），
    版本号可能输出到 stdout 或 stderr，两者都检查。
    """
    rc, _, _ = _run_conda_full(["CRISPResso", "--help"])
    if rc != 0:
        return False, "未安装"

    # 已安装：尝试从 --version 提取版本号
    _, v_stdout, v_stderr = _run_conda_full(["CRISPResso", "--version"])
    lines = [l.strip() for l in (v_stdout + "\n" + v_stderr).splitlines() if l.strip()]
    label = "\n".join(lines[-2:]) if lines else "已安装"
    return True, label


class ToolDetector(QThread):
    """后台探测工具是否安装，避免在窗口构造时阻塞主线程。

    发出 ``detected(bool, str)``，第一个参数表示是否就绪，第二个参数是版本标签。
    """

    detected = pyqtSignal(bool, str)

    def __init__(self, detect_func, parent=None):
        super().__init__(parent)
        self._detect_func = detect_func

    def run(self):
        try:
            ok, label = self._detect_func()
        except Exception as e:  # noqa: BLE001
            print("环境探测失败:", e)
            ok, label = False, "未安装"
        self.detected.emit(ok, label)


# ---------------------------------------------------------------------------
# GUI 辅助：并发数选择器
# ---------------------------------------------------------------------------

def add_parallel_selector(parent, layout):
    """向 ``layout`` 插入「外层并发数 + 内层线程数」设置，返回 ``(外层, 内层)`` 两个 QSpinBox。

    用于 CRISPResso 分析窗口（BE / HDR-PE / NHEJ）。两个值变化时自动保存到
    ``~/.NGS_Tools/config.json``，下次启动自动恢复。
    """
    # 外层并发样本数
    row1 = QHBoxLayout()
    label1 = QLabel("并发样本数（外层进程）：", parent)
    outer = QSpinBox(parent)
    outer.setRange(1, 256)
    outer.setValue(default_parallel())
    outer.setToolTip("同时运行的 CRISPResso 进程数。总内存 ≈ 该值 × 单样本内存。")
    row1.addWidget(label1)
    row1.addWidget(outer)
    row1.addStretch(1)
    layout.addLayout(row1)

    # 内层每样本线程数（-p）
    row2 = QHBoxLayout()
    label2 = QLabel("每样本线程数（内层 -p）：", parent)
    inner = QSpinBox(parent)
    inner.setRange(1, 64)
    inner.setValue(default_processes())
    inner.setToolTip("传给 CRISPResso 的 -p 参数，即每个样本内部使用的线程数。")
    row2.addWidget(label2)
    row2.addWidget(inner)
    row2.addStretch(1)
    layout.addLayout(row2)

    hint = QLabel(
        "提示：外层 × 内层 ≈ 总线程数，建议不要超过 CPU 逻辑核数，否则进程间互相争抢，反而更慢。",
        parent,
    )
    hint.setWordWrap(True)
    hint.setStyleSheet("color: gray;")
    layout.addWidget(hint)

    outer.valueChanged.connect(lambda v: set_config("parallel", v))
    inner.valueChanged.connect(lambda v: set_config("crispresso_processes", v))

    return outer, inner


# ---------------------------------------------------------------------------
# 通用表格 / 文件操作 Mixin
# ---------------------------------------------------------------------------

class TableWindowMixin:
    """为五个 GUI 窗口提供通用的表格与文件选择操作。

    依赖以下控件（五个窗口均已具备）：
    ``tableWidget`` / ``label`` / ``label_selection`` / ``checkBox_auto_fill_col`` /
    ``plainTextEdit_readIllumina`` / ``lineEdit_FqDir`` / 以及各 pushButton_* 按钮。
    """

    # 临时保存表格用的 Excel 路径（子类可覆盖）。
    TEMP_EXCEL_PATH = ".tmp.xlsx"

    # ------------------------------------------------------------------ 初始化

    def setupTableUI(self):
        """初始化表格元信息并连接通用信号，替代各模块重复的 __init__ 代码。"""
        self.selected_rows = []
        table = self.tableWidget
        self.col_names = []
        self.col_name_locations = {}
        for col in range(table.columnCount()):
            name = table.horizontalHeaderItem(col).text()
            self.col_names.append(name)
            self.col_name_locations[name] = col

        self.plainTextEdit_readIllumina.dropped.connect(self.autoInput)
        table.selectColumn(0)
        table.itemSelectionChanged.connect(self.showSelection)
        table.clicked.connect(self.disableAutoFill)

        self.pushButton_add_line.clicked.connect(self.addLine)
        self.pushButton_del_lines.clicked.connect(self.delLine)
        self.pushButton_import_from_sheet.clicked.connect(self.importFromSheet)
        self.pushButton_export_sheet.clicked.connect(self.exportSheet)
        self.pushButton_clear_table.clicked.connect(self.clearTable)
        self.pushButton_openFqDir.clicked.connect(self.openFolder)

    def _setLabelLyric(self):
        """把标签栏设置为一句诗词（或兜底文案）。"""
        self.label.setText(getLyric())

    # ------------------------------------------------------------------ 表格操作

    def addLine(self):
        """在表格末尾追加一行空行。"""
        table = self.tableWidget
        new_row = table.rowCount()
        table.setRowCount(new_row + 1)
        for col in range(table.columnCount()):
            table.setItem(new_row, col, QTableWidgetItem(""))

    def delLine(self):
        """删除选中的行（从后往前删，避免索引偏移）。"""
        rows = sorted(set(self.selected_rows), reverse=True)
        table = self.tableWidget
        for row in rows:
            if 0 <= row < table.rowCount():
                table.removeRow(row)
        self.selected_rows = []

    def showSelection(self):
        """更新选中行提示，并实现「自动向下填充」。"""
        selection = self.tableWidget.selectedIndexes()
        rows = []
        names = []
        seen = set()
        for index in selection:
            row = index.row()
            if row in seen:
                continue
            seen.add(row)
            try:
                name = self.tableWidget.item(row, 0).text()
            except AttributeError:
                name = ""
            rows.append(row)
            names.append(name)

        if len(rows) > 10:
            self.label_selection.setText("选中了" + str(len(rows)) + "个")
        else:
            self.label_selection.setText(str(names))
        self.selected_rows = rows

        if not self.checkBox_auto_fill_col.isChecked():
            return
        col = self.tableWidget.currentColumn()
        if col < 0:
            return
        try:
            first_data = self.tableWidget.item(rows[0], col).text()
        except (IndexError, AttributeError):
            first_data = ""
        for row in rows:
            self.tableWidget.setItem(row, col, QTableWidgetItem(first_data))

    def clearTable(self):
        """清空表格内容。"""
        self.tableWidget.clearContents()
        self.tableWidget.setRowCount(0)
        self._setLabelLyric()

    def disableAutoFill(self):
        """点击表格时关闭自动填充，避免误覆盖。"""
        self.checkBox_auto_fill_col.setChecked(False)

    # ------------------------------------------------------------------ 导入导出

    def exportSheet(self, tem_save=False):
        """把表格内容导出为 Excel。``tem_save=True`` 时导出到临时文件。"""
        self._setLabelLyric()
        if tem_save:
            file_path = self.TEMP_EXCEL_PATH
        else:
            file_path, _ = QFileDialog.getSaveFileName(self, "存", "", "excel(*.xlsx)")
            if not file_path:
                return
            if not file_path.endswith(".xlsx"):
                file_path += ".xlsx"

        import pandas as pd

        sheet = pd.DataFrame(columns=self.col_names)
        table = self.tableWidget
        for row in range(table.rowCount()):
            data = []
            for col in range(len(self.col_names)):
                item = table.item(row, col)
                data.append(item.text() if item is not None else "")
            sheet.loc[row] = data

        sheet.to_excel(file_path)
        return file_path

    def importFromSheet(self):
        """从 Excel 导入表格内容。"""
        file_path, _ = QFileDialog.getOpenFileName(self, "导入", "", "excel(*.xlsx)")
        self._setLabelLyric()
        if not file_path:
            return

        import pandas as pd

        sheet = pd.read_excel(file_path, index_col=0)
        table = self.tableWidget
        table.clearContents()
        table.setRowCount(len(sheet.index))
        n_cols = min(len(sheet.columns), table.columnCount())
        for row in range(len(sheet.index)):
            for col in range(n_cols):
                try:
                    text = str(sheet.iloc[row, col])
                except Exception:  # noqa: BLE001
                    text = ""
                if text == "nan":
                    text = ""
                table.setItem(row, col, QTableWidgetItem(text))

    # ------------------------------------------------------------------ 文件/路径

    def autoInput(self):
        """拖拽文件夹到输入框后，解析出本地路径。"""
        self._setLabelLyric()
        raw = self.plainTextEdit_readIllumina.toPlainText().strip()
        folder = unquote(raw)
        if folder.startswith("file://"):
            folder = folder[len("file://"):]
        self.plainTextEdit_readIllumina.setPlainText(folder)

    def chooseFolder(self, title="选择数据文件夹"):
        """弹出文件夹选择对话框并写入输入框。"""
        path = QFileDialog.getExistingDirectory(self, title)
        if path:
            self.plainTextEdit_readIllumina.setPlainText(path)

    def setSavePath(self):
        """弹出目录选择对话框并写入结果路径输入框。"""
        save_path = QFileDialog.getExistingDirectory(self, "选路径")
        if not save_path:
            return False
        self.lineEdit_FqDir.setText(save_path)
        return save_path

    def openFolder(self):
        """用系统文件管理器打开结果文件夹。"""
        path = self.lineEdit_FqDir.text()
        if not path:
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(path))

    # ------------------------------------------------------------------ 依赖安装

    def installDependence(self, detect_func, install_button):
        """安装依赖（conda / bcl2fastq / CRISPResso2）并刷新安装状态。

        :param detect_func: 探测函数，如 :func:`detect_bcl2fastq`。
        :param install_button: 安装按钮，安装成功后隐藏。
        """
        self.label.setText("正在安装，请少安毋躁")
        from PyQt5.QtWidgets import QMessageBox

        QMessageBox.about(self, "提示", "注意，点了ok后，界面将卡住不动，不要关闭该程序！")
        self._setLabelLyric()

        import checkEnv
        try:
            checkEnv.check()
        except Exception as e:  # noqa: BLE001 - 安装失败时给提示，而不是让程序崩溃退出
            print("环境安装失败:", e)
            QMessageBox.about(
                self,
                "安装失败",
                "环境安装过程中出错：\n\n"
                + str(e)
                + "\n\n请查看终端输出定位问题（常见原因：网络或 conda 源不可用）。",
            )
            return

        try:
            ok, label = detect_func()
        except Exception as e:  # noqa: BLE001
            print("安装后探测失败:", e)
            ok, label = False, "未安装"

        self.label_version.setText(label if ok else "未安装")
        install_button.setVisible(not ok)

        QMessageBox.about(self, "done", "安装进程已经结束，下面是安装详情\n" + label)


# ---------------------------------------------------------------------------
# 便捷子进程运行（供后台线程使用）
# ---------------------------------------------------------------------------

def run_conda_command(command_str):
    """在 NGS 环境中运行一条完整命令（字符串），返回 Popen 对象。

    直接调用环境内可执行文件（不走 ``conda run``，省去每次的激活开销），
    并把环境 bin 目录注入 ``PATH``，使 CRISPResso 能调起 bowtie2/samtools 等依赖；
    ``start_new_session=True`` 使其进入独立进程组，便于调用方整组终止。
    """
    tokens = shlex.split(command_str)
    if not tokens:
        raise ValueError("empty command: %r" % command_str)

    exe = os.path.join(CONDA_ENV_BIN, tokens[0])
    full_env = dict(os.environ)
    full_env["PATH"] = CONDA_ENV_BIN + os.pathsep + full_env.get("PATH", "")
    full_env.setdefault("CONDA_PREFIX", CONDA_ENV_DIR)
    full_env.setdefault("CONDA_DEFAULT_ENV", CONDA_ENV)

    return subprocess.Popen(
        [exe] + tokens[1:],
        env=full_env,
        start_new_session=True,
    )
