# -*- coding: utf-8 -*-
"""HDR / PE（先导编辑）分析：调用 CRISPResso2 并汇总结果。"""

import os
import time
import zipfile

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
from gui_PE import Ui_CRISPResso


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
            sample = str(ref.loc[i]["样品名"])
            sg1 = ref.loc[i]["sg1"]
            sg2 = ref.loc[i]["sg2"]
            seqPair = []

            splitor = self.lineEdit_split.text().strip()
            for f in fileList:
                if (sample + splitor) in f:
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
            else:
                print(sample + " not found")
                continue

            if (str(sg2) != "nan") and ("nan" != str(sg1)):
                sg = sg1.strip() + "," + sg2.strip()
            else:
                sg = str(sg1) + str(sg2)
                sg = sg.replace("nan", "")

            amplicon = ref.loc[i]["原始序列"]
            hdrRef = ref.loc[i]["修改后序列"]

            if len(seqPair) == 1:
                cmd = (
                    "CRISPResso -r1 %s -a %s -g %s -e %s %s%s -o %s/%s"
                    % (seqPair[0], amplicon, sg, hdrRef, parameter, proc_arg, output_path, sample)
                )
            elif len(seqPair) == 2:
                cmd = (
                    "CRISPResso -r1 %s -r2 %s -a %s -g %s -e %s %s%s -o %s/%s"
                    % (seqPair[0], seqPair[1], amplicon, sg, hdrRef, parameter, proc_arg, output_path, sample)
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

        result = pd.DataFrame(columns=[
            "描述", "正确编辑占总体的比例", "正确编辑占总编辑的比例",
            "Indel占总体比例", "NHEJ占总体体比例", "总读数", "实际使用读数",
        ])

        for i in ref.index:
            name = str(ref.loc[i, "样品名"].strip())
            result.loc[name, "描述"] = ref.loc[i, "描述"]
            resultDir = output_path + "/" + name

            logFile = allelesFrequencyTable = resultFile = ""
            try:
                os.listdir(resultDir)
            except OSError:
                result.loc[name, "正确编辑占总体的比例"] = "无测序文件"
                continue

            for f in os.listdir(resultDir):
                if "html" in f or "ipynb" in f:
                    continue
                folder = f
                logFile = resultDir + "/" + folder + "/CRISPResso_RUNNING_LOG.txt"
                allelesFrequencyTable = resultDir + "/" + folder + "/Alleles_frequency_table.zip"
                resultFile = resultDir + "/" + folder + "/CRISPResso_quantification_of_editing_frequency.txt"

            if not os.path.isfile(logFile):
                result.loc[name, "正确编辑占总体的比例"] = "No enough reads"
                print(name + "error, 未进行CRISPResso分析")
                continue

            try:
                with open(logFile) as log:
                    content = log.read()
                if "ERROR" in content:
                    errorResults.append(name)
                    result.loc[name, "正确编辑占总体的比例"] = "No enough reads"
                    for line in content.splitlines():
                        if "ERROR" in line:
                            print(name + line)
                    continue

                alleles_zip = zipfile.ZipFile(allelesFrequencyTable)
                alleles_zip.extractall(resultDir + "/" + folder + "/")
                alleles_zip.close()

                ambiguousIndel = 0
                alleles_df = pd.read_csv(
                    resultDir + "/" + folder + "/Alleles_frequency_table.txt", sep="\t"
                )
                for j in alleles_df.index:
                    if alleles_df.loc[j, "Reference_Name"] == "AMBIGUOUS_Reference":
                        if alleles_df.loc[j, "n_inserted"] + alleles_df.loc[j, "n_deleted"] > 0:
                            ambiguousIndel += alleles_df.loc[j, "#Reads"]

                resultFrame = pd.read_csv(resultFile, sep="\t")
                HDR_unmodified = resultFrame.loc[1, "Unmodified"]
                allHDR = resultFrame.loc[1, "Reads_aligned"]
                HDR_modified = resultFrame.loc[1, "Modified"]
                reads_aligned = resultFrame.loc[1, "Reads_aligned_all_amplicons"]
                reads = resultFrame.loc[1, "Reads_in_input"]
                NHEJreads = resultFrame.loc[0, "Modified"]
                insertion = int(resultFrame.loc[0, "Insertions"]) + int(resultFrame.loc[1, "Insertions"])
                deletion = int(resultFrame.loc[0, "Deletions"]) + int(resultFrame.loc[1, "Deletions"])
                insertionAndDeletion = (
                    int(resultFrame.loc[0, "Insertions and Deletions"])
                    + int(resultFrame.loc[1, "Insertions and Deletions"])
                )

                if reads_aligned < 1500:
                    result.loc[name, "正确编辑占总体的比例"] = "No enough reads"
                    print(name, "reads 过少")
                    continue

                result.loc[name, "总读数"] = reads
                result.loc[name, "实际使用读数"] = reads_aligned

                def _percent(numerator, denominator):
                    try:
                        return "%.2f%%" % (float(numerator) / float(denominator) * 100)
                    except Exception:
                        return "%.2f%%" % 0.0

                result.loc[name, "正确编辑占总体的比例"] = _percent(HDR_unmodified, reads_aligned)
                result.loc[name, "正确编辑占总编辑的比例"] = _percent(HDR_unmodified, allHDR)
                result.loc[name, "NHEJ占总体体比例"] = _percent(NHEJreads, reads_aligned)
                result.loc[name, "Indel占总体比例"] = _percent(
                    insertion + deletion + ambiguousIndel - insertionAndDeletion, reads_aligned
                )
            except Exception as e:  # noqa: BLE001
                print(e)
                continue

        time1 = str(time.ctime())
        result.loc["备注", "正确编辑占总体的比例"] = (
            "有发生insertion 或者 deletetion的，或者两者同时发生的算为一个indel。统计来源：与原始amplicon类似的reads（NHEJ），"
            "与预期序列类似的（imperfect HDR），与原始、预期都相似但无法判断的reads（AMBIGUOUS）"
        )
        result.loc["Method", "正确编辑占总体的比例"] = (
            "Modified genome was amplified and sequenced using illumina MiniSeq®. Each amlicon-seq data was analysed wiht "
            "CRISPResso2 and summarized by a home-made script. The indel is regard as the reads with insertion or deletion, "
            "but subsitution. Data analysis was performed by Qiqin Mo, and the code is avalibele at "
            "https://github.com/Hanhui-Ma-Lab/Script_for_Amplicon-seq "
        )
        result.to_excel(output_path + "/结果汇总.xlsx")
        ref.to_excel(output_path + "/原始信息表格.xlsx")
        QMessageBox.about(self, "Done", "已完成！\n开始时间：" + self.time0 + "\n结束时间：" + time1)


if __name__ == "__main__":
    import sys

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    win = MyMainWin()
    win.show()
    sys.exit(app.exec_())
