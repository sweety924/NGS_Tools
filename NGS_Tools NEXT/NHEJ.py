# -*- coding: utf-8 -*-
"""NHEJ 分析：调用 CRISPResso2 并汇总结果。"""

import os
import time

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox

import pandas as pd

from background_task import bgCRISPResso2, lyricThread
from common import (
    TableWindowMixin,
    ToolDetector,
    add_parallel_selector,
    detect_crispresso,
    lyric_enabled,
    process_arg,
)
from gui_NHEJ import Ui_CRISPResso


class MyMainWin(QMainWindow, TableWindowMixin, Ui_CRISPResso):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        output = "使用CRISPResso2分析Fastq文件" + "\n\t\t\t" + "——Written by M.Q. at Ma lab, ShanghaiTech University"
        self.label.setText(output)

        self.setupTableUI()
        self.parallelSpin, self.processSpin = add_parallel_selector(self, self.verticalLayout_5)
        self.groupBox_status.setVisible(False)
        self.pushButton_stop.setVisible(False)

        self.lyricThread = lyricThread()
        self.lyricThread.updated.connect(self.updateLyric)

        self.pushButton_install.clicked.connect(
            lambda: self.installDependence(detect_crispresso, self.pushButton_install)
        )
        self.pushButton_generateFq.clicked.connect(self.start)
        self.pushButton_chooseFolder.clicked.connect(
            lambda: self.chooseFolder("选择fastq数据所在的文件夹")
        )
        self.pushButton_stop.clicked.connect(self.stopTread)

        self._detector = ToolDetector(detect_crispresso, self)
        self._detector.detected.connect(self._onVersionDetected)
        self._detector.start()

    def _onVersionDetected(self, ok, label):
        self.label_version.setText(label)
        self.pushButton_install.setVisible(not ok)

    def updateLyric(self, lyric):
        self.label.setText(lyric)

    def stopTread(self):
        self.thread.stop()
        self.thread.wait(3000)
        self.summarize()
        QMessageBox.about(
            self,
            "停止",
            "已停止，目前已经分析的部分样品将会被汇总。\n\n 在停止的这个瞬间，后台尚有数个样品正在分析，可能会稍微多占用几分钟电脑资源，无需理会即可。",
        )

    # ------------------------------------------------------------------ 功能区

    def start(self):
        if lyric_enabled():
            self.lyricThread.start()
        if self.plainTextEdit_readIllumina.toPlainText() == "":
            QMessageBox.about(self, "Fastq folder not set", "ERROR:\n必须指定fastq文件所在的文件夹！")
            return
        if not self.setSavePath():
            return
        self.label.setText(""" ε٩(๑> ₃ <)۶з  正在运行，界面会卡住很久，请少安毋躁♥""")
        output_path = self.lineEdit_FqDir.text()
        path = self.plainTextEdit_readIllumina.toPlainText()
        if path == "":
            return

        self.exportSheet(tem_save=True)
        ref = pd.read_excel(".tmp.xlsx", index_col=0)
        self._setLabelLyric()
        parameter = "  " + self.plainTextEdit_parameters.toPlainText().replace("\n", "  ")
        proc_arg = process_arg(self.processSpin.value())  # CRISPResso 内部多线程 -p 参数

        cmdList = []
        fileList = os.listdir(path)
        task_sum = len(ref.index)
        task_count = 0

        for i in ref.index:
            task_count += 1
            sample = str(ref.loc[i]["样品名"]).strip()
            sg = ref.loc[i]["sg"]
            seqPair = []

            splitor = self.lineEdit_split.text().strip()
            for f in fileList:
                seq_name = f.split(splitor)[0]
                if seq_name == sample:
                    seqPair.append(path + "/" + f)

            if seqPair:
                try:
                    ref.loc[i, "测序文件2"] = os.path.basename(seqPair[0])
                except Exception:
                    ref.loc[i, "测序文件2"] = "无文件"
                try:
                    ref.loc[i, "测序文件1"] = os.path.basename(seqPair[1])
                except Exception:
                    ref.loc[i, "测序文件1"] = "无文件"

                if len(seqPair) != 2:
                    print(sample)
                    print(seqPair)
            else:
                print(sample + " not found")
                continue

            amplicon = ref.loc[i]["原始序列"]

            if len(seqPair) == 2:
                cmd = (
                    "CRISPResso --base_editor_output -r1 %s -r2 %s -a %s -g %s %s%s -o %s/%s"
                    % (seqPair[0], seqPair[1], amplicon, sg, parameter, proc_arg, output_path, sample)
                )
            elif len(seqPair) == 1:
                cmd = (
                    "CRISPResso --base_editor_output -r1 %s -a %s -g %s %s%s -o %s/%s"
                    % (seqPair[0], amplicon, sg, parameter, proc_arg, output_path, sample)
                )
            else:
                QMessageBox.about(
                    self,
                    "Error",
                    f"出错🌶\n\n 根据样品名在文件夹中找到多个文件：\n{seqPair}，\n\n请把非测序文件移出测序文件夹，或更改识别样品名模式。",
                )
                return
            cmdList.append(cmd)

        self.ref = ref
        self.time0 = str(time.ctime())
        self.task_sum = task_sum
        self.progressBar.setRange(0, 0)
        self.progressBar.setValue(0)
        self.groupBox_status.setVisible(True)
        self.pushButton_generateFq.setEnabled(False)

        self.thread = bgCRISPResso2(cmdList=cmdList, max_thread=self.parallelSpin.value())
        self.thread.updated.connect(self.updateStatus)
        self.thread.finished.connect(self.summarize)
        self.thread.start()

    def updateStatus(self, num):
        self.progressBar.setRange(0, self.task_sum)
        self.progressBar.setValue(int(self.progressBar.value()) + int(num))

    def summarize(self):
        if getattr(self, "_summarized", False):
            return
        self._summarized = True
        self.progressBar.setValue(0)
        self.lyricThread.stop()
        self.groupBox_status.setVisible(False)
        self.pushButton_generateFq.setEnabled(True)

        ref = self.ref
        output_path = self.lineEdit_FqDir.text()
        errorResults = []

        result = pd.DataFrame(columns=["描述", "NHEJ占总体的比例", "总读数", "实际使用读数"])

        for i in ref.index:
            name = str(ref.loc[i, "样品名"].strip())
            result.loc[name, "描述"] = ref.loc[i, "描述"]
            resultDir = output_path + "/" + name

            logFile = resultFile = ""
            try:
                os.listdir(resultDir)
            except OSError:
                result.loc[name, "NHEJ占总体的比例"] = "无测序文件"
                continue

            for f in os.listdir(resultDir):
                if "html" in f or "ipynb" in f:
                    continue
                folder = f
                logFile = resultDir + "/" + folder + "/CRISPResso_RUNNING_LOG.txt"
                resultFile = resultDir + "/" + folder + "/CRISPResso_quantification_of_editing_frequency.txt"

            if not os.path.isfile(logFile):
                result.loc[name, "NHEJ占总体的比例"] = "No enough reads"
                print(name + "error, 未进行CRISPResso分析")
                continue

            try:
                with open(logFile) as log:
                    content = log.read()
                if "ERROR" in content:
                    errorResults.append(name)
                    result.loc[name, "NHEJ占总体的比例"] = "No enough reads"
                    for line in content.splitlines():
                        if "ERROR" in line:
                            print(name + line)
                    continue

                resultFrame = pd.read_csv(resultFile, sep="\t")
                reads_aligned = resultFrame.loc[0, "Reads_aligned_all_amplicons"]
                reads = resultFrame.loc[0, "Reads_in_input"]
                NHEJreads = resultFrame.loc[0, "Modified"]

                if reads_aligned < 1500:
                    result.loc[name, "NHEJ占总体的比例"] = "No enough reads"
                    print(name, "reads 过少")
                    continue

                result.loc[name, "总读数"] = reads
                result.loc[name, "实际使用读数"] = reads_aligned

                try:
                    result.loc[name, "NHEJ占总体的比例"] = "%.2f%%" % (float(NHEJreads) / float(reads_aligned) * 100)
                except Exception:
                    result.loc[name, "NHEJ占总体的比例"] = "%.2f%%" % 0.0
            except Exception as e:  # noqa: BLE001
                print(e)
                continue

        result.to_excel(output_path + "/结果汇总.xlsx")
        ref.to_excel(output_path + "/原始信息表格.xlsx")
        time1 = str(time.ctime())
        QMessageBox.about(self, "Done", "已完成！\n开始时间：" + self.time0 + "\n结束时间：" + time1)


if __name__ == "__main__":
    import sys

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    win = MyMainWin()
    win.show()
    sys.exit(app.exec_())
