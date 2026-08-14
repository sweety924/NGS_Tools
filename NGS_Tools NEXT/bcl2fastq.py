# -*- coding: utf-8 -*-
"""illumina 下机数据拆分（bcl2fastq）图形界面。"""

import os

from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QMessageBox

import pandas as pd

import background_task
from common import (
    TableWindowMixin,
    ToolDetector,
    bash_header,
    detect_bcl2fastq,
    reverseDNA,
)
from gui_bcl2fq import Ui_BCL2Fastq


class MyMainWin(QMainWindow, TableWindowMixin, Ui_BCL2Fastq):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        output = "BCL2Fastq处理" + "\n\t\t\t" + "——Written by M.Q. at ShanghaiTech University"
        self.label.setText(output)

        self.setupTableUI()
        self.progressBar.setVisible(False)

        self.pushButton_install_bcl2fq.clicked.connect(
            lambda: self.installDependence(detect_bcl2fastq, self.pushButton_install_bcl2fq)
        )
        self.pushButton_generateFq.clicked.connect(self.writeSampleSheet)
        self.pushButton_chooseFolder.clicked.connect(
            lambda: self.chooseFolder("选择下机数据文件夹")
        )

        # 非阻塞探测 bcl2fastq，避免启动时卡住界面。
        self._detector = ToolDetector(detect_bcl2fastq, self)
        self._detector.detected.connect(self._onVersionDetected)
        self._detector.start()

    def _onVersionDetected(self, ok, label):
        self.label_version.setText(label)
        self.pushButton_install_bcl2fq.setVisible(not ok)

    # ------------------------------------------------------------------ 功能区

    def writeSampleSheet(self):
        header = """[Header],,,,,,,
IEMFileVersion,5,,,,,,
Date,2023/1/1,,,,,,
Workflow,GenerateFASTQ,,,,,,
Application,HiSeq FASTQ Only,,,,,,
Instrument Type,MiniSeq,,,,,,
Assay,Ampliseq,,,,,,
Index Adapters,Illumina Universal Adapters,,,,,,
Chemistry,DNA,,,,,,
,,,,,,,
[Reads],,,,,,,
,,,,,,,
,,,,,,,
,,,,,,,
[Data],,,,,,,"""
        sheet = pd.DataFrame(
            columns=[
                "Sample_ID", "Index_Plate_Well", "I5_Index_ID", "index2",
                "I7_Index_ID", "index", "Sample_Project", "Description",
            ]
        )
        table = self.tableWidget

        for row in range(table.rowCount()):
            try:
                ID = table.item(row, 0).text()
                I5_ID = table.item(row, 1).text()
                I5_seq = table.item(row, 2).text()
                I7_ID = table.item(row, 3).text()
                I7_seq = table.item(row, 4).text()
                description = table.item(row, 5).text()

                if self.checkBox_reI5.isChecked():
                    I5_seq = reverseDNA(I5_seq)
                if self.checkBox_reI7.isChecked():
                    I7_seq = reverseDNA(I7_seq)

                sheet.loc[row, "Sample_ID"] = ID
                sheet.loc[row, "I5_Index_ID"] = I5_ID
                sheet.loc[row, "index2"] = I5_seq
                sheet.loc[row, "I7_Index_ID"] = I7_ID
                sheet.loc[row, "index"] = I7_seq
                sheet.loc[row, "Description"] = description
            except AttributeError:
                continue

        illumina_dir = self.plainTextEdit_readIllumina.toPlainText()
        if illumina_dir == "":
            QMessageBox.about(self, "错误", "下机文件夹未填写")
            return

        sample_sheet_path = os.path.join(illumina_dir, "SampleSheet.csv")
        tmp_path = os.path.join(illumina_dir, "SampleSheet0.csv")
        sheet.to_csv(tmp_path, index=False)
        with open(tmp_path, "r") as f:
            sheet_text = f.read()
        with open(sample_sheet_path, "w") as f:
            f.write(header + "\n" + sheet_text)

        if not self.setSavePath():
            return
        self.label.setText(""" ε٩(๑> ₃ <)۶з  正在运行，界面会卡住很久，请少安毋躁♥""")
        output_path = self.lineEdit_FqDir.text()

        cmd = (
            "bcl2fastq -R " + illumina_dir.strip() + " -o " + output_path
            + " " + self.lineEdit_parameter.text()
            + " --sample-sheet " + illumina_dir.strip() + "/SampleSheet.csv  "
        )
        with open(".run.sh", "w") as f:
            content = bash_header() + "echo 开始分析\n{\n" + cmd + "\n}&\nwait"
            f.write(content)
            self.cmd = cmd

        task = background_task.bcl2fastqThread()
        task.finished.connect(self.finish)
        task.start()
        self.progressBar.setVisible(True)
        self.pushButton_generateFq.setEnabled(False)

    def finish(self, msg):
        self.progressBar.setVisible(False)
        self.pushButton_generateFq.setEnabled(True)
        QMessageBox.about(
            self,
            "运行结果",
            msg
            + "\n\n以上为本次运行结果的最后一行输出。\n\n若有错请在终端重新运行，并根据输出修改错误。"
            "刚刚运行的指令为\n\n~/miniconda3/bin/conda run -n NGS "
            + self.cmd,
        )
        self._setLabelLyric()


if __name__ == "__main__":
    import sys

    QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling)
    app = QApplication(sys.argv)
    win = MyMainWin()
    win.show()
    sys.exit(app.exec_())
