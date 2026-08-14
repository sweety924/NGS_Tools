# -*- coding: utf-8 -*-
"""碱基编辑器（BE）分析：调用 CRISPResso2 并汇总结果。"""

import os
import re
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
    reverseDNA,
)
from gui_BE import Ui_CRISPResso


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
        self.newRef = pd.DataFrame(columns=ref.columns)
        self.newRef.to_excel(".tmp2.xlsx")

        for i in ref.index:
            try:
                sample = ref.loc[i, "样品名"]
                base_from = ref.loc[i, "原始碱基"].upper()
                base_to = ref.loc[i, "修改后碱基"].upper()
                edit_site = str(ref.loc[i, "最想看的位置"])
                if edit_site == "nan":
                    edit_site = 0
                output_name = sample + "_" + edit_site + "-" + base_from + "-" + base_to
                self.newRef.loc[output_name] = ref.loc[i]
            except Exception as e:  # noqa: BLE001
                print(e)
                continue

        self._setLabelLyric()
        parameter = "  " + self.plainTextEdit_parameters.toPlainText().replace("\n", "  ")
        proc_arg = process_arg(self.processSpin.value())  # CRISPResso 内部多线程 -p 参数

        cmdList = []
        fileList = os.listdir(path)
        seq_pairs = {}
        task_sum = len(self.newRef.index)
        task_count = 0

        for i in self.newRef.index:
            task_count += 1
            sample = str(self.newRef.loc[i]["样品名"]).strip()
            output_name = str(i).strip()
            sg = self.newRef.loc[i]["sg"]
            seqPair = []

            splitor = self.lineEdit_split.text().strip()
            for f in fileList:
                seq_name = f.split(splitor)[0]
                if seq_name == sample:
                    seqPair.append(path + "/" + f)

            seq_pairs[sample] = seqPair

            if seqPair:
                try:
                    self.newRef.loc[i, "测序文件1"] = os.path.basename(seqPair[0])
                except Exception:
                    pass
                try:
                    self.newRef.loc[i, "测序文件2"] = os.path.basename(seqPair[1])
                except Exception:
                    print("只有一个文件，为单端测序")

                if len(seqPair) > 2:
                    print(sample)
                    print(seqPair)
                    QMessageBox.about(
                        self,
                        "Error",
                        f"出错🌶\n\n 根据样品名在文件夹中找到多个文件：\n{seq_pairs}，\n\n请把非测序文件移出测序文件夹，或更改识别样品名模式。",
                    )
                    return
            else:
                print(sample + " not found")
                continue

            amplicon = self.newRef.loc[i]["原始序列"]
            baseFrom = self.newRef.loc[i]["原始碱基"].upper()
            baseTo = self.newRef.loc[i]["修改后碱基"].upper()

            if sg.upper().strip() in reverseDNA(amplicon.upper()):
                amplicon = reverseDNA(amplicon)
                print("non edit strand provided, I'll reverse it.")

            center = str(int(len(sg) / 2))
            win = str(int((int(len(sg) / 2)) + len(sg) % 2))

            if len(seqPair) == 1:
                cmd = (
                    "CRISPResso --base_editor_output "
                    "-r1 %s -a %s -g %s --conversion_nuc_from %s --conversion_nuc_to %s "
                    "%s%s --quantification_window_center -%s -w %s --plot_window_size %s "
                    "-o %s/%s"
                    % (seqPair[0], amplicon, sg, baseFrom, baseTo, parameter, proc_arg, center, win, win, output_path, output_name)
                )
            else:  # len(seqPair) == 2
                cmd = (
                    "CRISPResso --base_editor_output "
                    "-r1 %s -r2 %s -a %s -g %s --conversion_nuc_from %s --conversion_nuc_to %s "
                    "%s%s --quantification_window_center -%s -w %s --plot_window_size %s "
                    "-o %s/%s"
                    % (seqPair[0], seqPair[1], amplicon, sg, baseFrom, baseTo, parameter, proc_arg, center, win, win, output_path, output_name)
                )
            cmdList.append(cmd)

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

        output_path = self.lineEdit_FqDir.text()
        errorResults = []

        position_cols = [str(k) for k in range(1, 41)]
        unspecific_cols = ["u" + str(k) for k in range(1, 41)]
        result = pd.DataFrame(columns=[
            "样品名", "描述", "原始碱基", "修改后碱基", "最想看的位置",
            "最想看的位置的效率", "测序深度", "各位点的特异性编辑效率",
            *position_cols, "各位点的非特异编辑效率", *unspecific_cols,
        ])

        for i in self.newRef.index:
            name = str(i)
            real_name = str(self.newRef.loc[i, "样品名"]).strip()
            resultDir = output_path + "/" + name

            desire_position = str(self.newRef.loc[i, "最想看的位置"])
            result.loc[name, "最想看的位置"] = desire_position
            result.loc[name, "样品名"] = real_name
            result.loc[name, "描述"] = str(self.newRef.loc[i, "描述"]).strip()

            logFile = infoFile = subsitutionFile = ""
            try:
                for f in os.listdir(resultDir):
                    if "html" in f or "ipynb" in f:
                        continue
                    folder = f
                    logFile = resultDir + "/" + folder + "/CRISPResso_RUNNING_LOG.txt"
                    infoFile = resultDir + "/" + folder + "/CRISPResso2_info.json"
                    subsitutionFile = resultDir + "/" + folder + "/Quantification_window_substitution_frequency_table.txt"
                    if not os.path.exists(logFile) or not os.path.exists(infoFile) or not os.path.exists(subsitutionFile):
                        continue
            except OSError as e:
                print(e)
                continue

            try:
                with open(logFile) as log:
                    content = log.read()
                if "ERROR" in content:
                    errorResults.append(name)
                    result.loc[name, "原始碱基"] = "No enough reads"
                    print(name + " error")
                    continue

                with open(infoFile) as info_fd:
                    info = info_fd.read()
                baseFrom = re.compile('"conversion_nuc_from": "(.)"').findall(info)[0].upper()
                baseTo = re.compile('"conversion_nuc_to": "(.)"').findall(info)[0].upper()
                sgFile = re.compile(r'Selected_nucleotide_frequency_table_around_sgRNA_.*?\.txt?').search(info).group()

                result.loc[name, "原始碱基"] = baseFrom
                result.loc[name, "修改后碱基"] = baseTo

                editTable = pd.read_csv(resultDir + "/" + folder + "/" + sgFile, sep="\t")
                for location in editTable.columns:
                    if "Unn" in location:
                        continue
                    editLocation = str(location[1:])
                    baseReads = {
                        "A": int(editTable.loc[0, location]),
                        "C": int(editTable.loc[1, location]),
                        "G": int(editTable.loc[2, location]),
                        "T": int(editTable.loc[3, location]),
                        "N": int(editTable.loc[4, location]),
                        "-": int(editTable.loc[5, location]),
                    }
                    allReads = sum(baseReads.values())
                    if allReads == 0:
                        continue
                    editReads = "%.2f%%" % (float(baseReads[baseTo] / allReads) * 100)
                    result.loc[name, str(editLocation)] = editReads
                    result.loc[name, "测序深度"] = allReads

                    if str(int(editLocation)) == desire_position:
                        result.loc[name, "最想看的位置的效率"] = editReads

                subTable = pd.read_csv(subsitutionFile, sep="\t")
                for n, base in enumerate(subTable.columns):
                    try:
                        baseReads = {
                            "A": subTable.iloc[0, n + 1],
                            "C": subTable.iloc[1, n + 1],
                            "G": subTable.iloc[2, n + 1],
                            "T": subTable.iloc[3, n + 1],
                            "N": subTable.iloc[4, n + 1],
                        }
                        allSubReads = sum(baseReads.values())
                        if allSubReads == 0:
                            continue
                        unspecificEditReads = "%.2f%%" % (
                            float((allSubReads - baseReads[baseFrom] - baseReads[baseTo]) / allSubReads) * 100
                        )
                        result.loc[name, "u" + str(n + 1)] = unspecificEditReads
                    except Exception as e:  # noqa: BLE001
                        print(e)
                        continue
            except Exception as e:  # noqa: BLE001
                print(e)
                continue

        self.time1 = str(time.ctime())
        result.to_excel(output_path + "/结果汇总.xlsx")
        self.newRef.to_excel(output_path + "/原始信息表格.xlsx")
        QMessageBox.about(self, "Done", "已完成！\n开始时间：" + self.time0 + "\n结束时间：" + self.time1)


if __name__ == "__main__":
    import sys

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    win = MyMainWin()
    win.show()
    sys.exit(app.exec_())
