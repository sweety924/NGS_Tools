# -*- coding: utf-8 -*-
"""Fastq 文件二次拆分（按索引序列拆分已拆好的 fastq 文件）。"""

import os
import time

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox

import pandas as pd

from background_task import bgThread, getUid, monitorThread
from common import TableWindowMixin, bash_header
from gui_demultiplex import Ui_BCL2Fastq


def extractSample():
    """写入二次拆分的 shell 脚本（.extract.sh）。

    参数约定：``$1`` 索引1，``$2`` 索引2，``$3/$4`` 输入 R1/R2，
    ``$5/$6`` 输出 R1/R2，``$7`` 索引上游序列长度范围。
    """
    script = """#!/bin/bash
#the input $1 is R1-index
#the input $2 is R2-index
#the input $3 is R1 file
#the input $4 is R2 file
#the input $5 is R1 output
#the input $6 is R2 output
#the input $7 is the length range of index upstream sequence.

index1=$1
index2=$2
r1=$3
r2=$4
o1=$5
o2=$6
d=$7
session=$(cat /proc/sys/kernel/random/uuid)

zcat ${r1} |grep -A 2 -B 1  --no-group-separator -E  "^.{0,$d}${index1}" >  ${index1}.${session}.tmp.txt
n=$(cat  ${index1}.${session}.tmp.txt |grep @|wc -l)
echo "find $n record with barcode $index1"

grep  --no-group-separator -oE '^@[^ ]+ ' ${index1}.${session}.tmp.txt > ${index1}.${session}.tmp.idx
n=$(cat  ${index1}.${session}.tmp.idx |grep @|wc -l)
echo "export $n barcode id"

zcat  ${r2} | grep  -A 3 --no-group-separator -F -f ${index1}.${session}.tmp.idx |grep -A 2 -B 1 --no-group-separator  -E "^.{0,$d}${index2}" > ${o2}
n=$(cat  ${o2} |grep @|wc -l)
echo "find $n record in r2"

grep  --no-group-separator -oE '^@[^ ]+ '  ${o2} > ${index1}.${index2}.${session}.tmp.idx
n=$(cat  ${index1}.${index2}.${session}.tmp.idx |grep @|wc -l)
echo "created $n id by r2"

cat  ${index1}.${session}.tmp.txt | grep  -A 3 --no-group-separator -F -f ${index1}.${index2}.${session}.tmp.idx > ${o1}
n=$(cat  ${o1} |grep @|wc -l)
echo "get $n record in r1"
rm -rf ${o1}.gz
rm -rf ${o2}.gz
gzip $o1
gzip $o2
rm -rf ${index1}.${session}.tmp.txt
rm -rf ${index1}.${session}.tmp.idx
rm -rf ${index1}.${index2}.${session}.tmp.idx
"""
    with open(".extract.sh", "w") as f:
        f.write(script)


class MyMainWin(QMainWindow, TableWindowMixin, Ui_BCL2Fastq):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        output = "BCL2Fastq处理" + "\n\t\t\t" + "——Written by M.Q. at ShanghaiTech University"
        self.label.setText(output)

        self.setupTableUI()
        self.groupBox_status.setVisible(False)
        self.pushButton_stop.setVisible(False)

        self.pushButton_generateFq.clicked.connect(self.start)
        self.pushButton_chooseFolder.clicked.connect(
            lambda: self.chooseFolder("选择 fastq.gz 数据文件夹")
        )
        self.pushButton_stop.clicked.connect(self.stopTread)

    def stopTread(self):
        self.thread.stop()
        self.monitor.stop()
        self.groupBox_status.setVisible(False)
        self.pushButton_generateFq.setEnabled(True)
        QMessageBox.about(self, "停止", "已停止")

    # ------------------------------------------------------------------ 功能区

    def start(self):
        if self.plainTextEdit_readIllumina.toPlainText() == "":
            QMessageBox.about(self, "Fastq folder not set", "ERROR:\n必须指定fastq文件所在的文件夹！")
            return
        if not self.setSavePath():
            return
        self.label.setText(""" ε٩(๑> ₃ <)۶з  正在运行，界面会卡住很久，请少安毋躁♥""")
        self.time0 = time.ctime()

        extractSample()
        output_path = self.lineEdit_FqDir.text()
        path = self.plainTextEdit_readIllumina.toPlainText()
        if path == "":
            return

        self.exportSheet(tem_save=True)
        ref = pd.read_excel(".tmp.xlsx", index_col=0)

        bashData = [bash_header()]
        authorInfo = """# This Script is generated automatically. Do not modify anything unless you know what you are doing.
                        # Script Author:\tMo Qiqin
                        # Contact:\tmoqq@shanghaitech.edu.cn
                        uid=$1
                        mkdir /tmp/${uid}
                        """
        bashData.append(authorInfo)

        thread = int(os.cpu_count())
        if thread < 8:
            thread = 8

        counter = 0
        cmdList = []
        fileList = os.listdir(path)
        seq_pairs = {}
        task_sum = len(ref.index)
        task_count = 0

        for i in ref.index:
            try:
                sample = str(ref.loc[i, "样品名"]).replace(" ", "")
                pool = str(ref.loc[i, "所在样品库"]).replace(" ", "")
                index1 = str(ref.loc[i, "索引序列1"]).strip()
                index2 = str(ref.loc[i, "索引序列2"]).strip()
            except Exception as e:  # noqa: BLE001
                print(e)
                continue

            seqPair = []
            for f in fileList:
                seq_name = f.split("_")[0]
                if seq_name == pool:
                    seqPair.append(path + "/" + f)

            seq_pairs[pool] = seqPair

            if not seqPair:
                print(pool + " not found")
                continue

            if len(seqPair) != 2:
                print(pool)
                print(seqPair)
                continue

            if "_R1" in os.path.split(seqPair[0])[1]:
                r1, r2 = seqPair[0], seqPair[1]
            else:
                r1, r2 = seqPair[1], seqPair[0]

            ref.loc[i, "测序文件1"] = sample + "_on_" + pool + "_R1.fastq"
            ref.loc[i, "测序文件2"] = sample + "_on_" + pool + "_R2.fastq"
            task_count += 1

            distance = self.lineEdit_distance.text().strip() or "10"
            cmd = (
                "bash .extract.sh {0} {1} {2} {3} {4}/{5}_on_{6}_R1.fastq {4}/{5}_on_{6}_R2.fastq {7}".format(
                    index1, index2, r1, r2, output_path, sample, pool, distance
                )
            )
            cmdList.append(cmd)

            CMD = "{\n" + cmd + "\n}&\n\n clear \n touch /tmp/${uid}/" + str(task_count) + "\n\n"
            bashData.append(CMD)
            counter += 1
            if counter == thread:
                bashData.append("\nwait\n")
                counter = 0

        bashData.append("\n wait \n rm -rf /tmp/${uid} \n")
        with open(".run.sh", "w") as f:
            f.write("".join(bashData))

        task_id = getUid()
        self.thread = bgThread(task_id)
        self.thread.finished.connect(self.summarize)
        self.ref = ref
        self.output_path = output_path

        self.monitor = monitorThread(task_id)
        self.progressBar.setRange(0, task_sum)

        self.thread.start()
        self.monitor.start()
        self.monitor.updated.connect(self.updateStatus)
        self.groupBox_status.setVisible(True)
        self.pushButton_generateFq.setEnabled(False)

    def updateStatus(self, status):
        self.progressBar.setValue(int(status))

    def summarize(self):
        self.monitor.stop()
        self.groupBox_status.setVisible(False)
        self.pushButton_generateFq.setEnabled(True)
        self._setLabelLyric()
        time1 = time.ctime()
        self.ref.to_excel(self.output_path + "/样品信息.xlsx")
        QMessageBox.about(self, "Done", "已完成！\n开始时间：" + self.time0 + "\n结束时间：" + time1)


if __name__ == "__main__":
    import sys

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    win = MyMainWin()
    win.show()
    sys.exit(app.exec_())
