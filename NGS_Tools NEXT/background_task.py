# -*- coding: utf-8 -*-
"""后台任务线程。

所有耗时操作（bcl2fastq 拆分、CRISPResso 批量分析、fastq 二次拆分等）都放到
QThread 中运行，避免阻塞 GUI 主线程。各线程提供 ``stop()`` 方法用于优雅停止，
取代直接调用 :meth:`QThread.terminate` 的暴力做法。
"""

import os
import signal
import subprocess
import time
import uuid

from PyQt5.QtCore import QThread, pyqtSignal

from common import default_parallel, getLyric, run_conda_command


def getUid():
    """生成一个随机 uid，用于 /tmp 下的任务目录。"""
    return str(uuid.uuid4())


def _kill_process_group(proc):
    """尽力终止一个子进程及其进程组（不抛异常）。"""
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception as e:  # noqa: BLE001
        print("终止子进程失败:", e)


class monitorThread(QThread):
    """统计 /tmp/<uid> 下完成的文件数，用于 fastq 二次拆分的进度显示。"""

    finished = pyqtSignal(str)
    updated = pyqtSignal(int)

    def __init__(self, uid="sdf", parent=None):
        super().__init__(parent)
        self.uid = uid
        self._stop = False

    def stop(self):
        self._stop = True

    def monitor(self):
        path = os.path.join("/tmp", self.uid)
        try:
            return len(os.listdir(path))
        except OSError:
            return 0

    def run(self):
        last_sum = 0
        while not self._stop:
            current = int(self.monitor())
            if current != last_sum:
                last_sum = current
                self.updated.emit(last_sum)
            self.msleep(500)


class bgThread(QThread):
    """运行 ``bash ./.run.sh <uid>``（fastq 二次拆分批处理脚本）。"""

    finished = pyqtSignal(str)
    updated = pyqtSignal(int)

    def __init__(self, uid="sdf", parent=None):
        super().__init__(parent)
        self.uid = uid
        self._proc = None
        self._stop = False

    def stop(self):
        self._stop = True
        _kill_process_group(self._proc)

    def run(self):
        try:
            self._proc = subprocess.Popen(
                ["bash", "./.run.sh", str(self.uid)],
                start_new_session=True,
            )
            self._proc.wait()
        except Exception as e:  # noqa: BLE001
            print("运行 .run.sh 失败:", e)
        # 被用户主动停止时不触发完成信号，避免误执行汇总。
        if not self._stop:
            self.finished.emit("done")


class bgRun(QThread):
    """在 conda 环境中运行单条 CRISPResso 命令。"""

    finished = pyqtSignal(str)

    def __init__(self, cmd="", parent=None):
        super().__init__(parent)
        self.cmd = cmd
        self._proc = None
        self._stop = False

    def stop(self):
        self._stop = True
        _kill_process_group(self._proc)

    def run(self):
        try:
            print("conda run -n NGS " + self.cmd)
            self._proc = run_conda_command(self.cmd)
            self._proc.wait()
        except Exception as e:  # noqa: BLE001
            print("运行命令失败:", self.cmd, e)
        finally:
            self.finished.emit(self.cmd)


class bgCRISPResso2(QThread):
    """CRISPResso 批量分析调度器。

    按 CPU 核数限制并发，逐个启动 :class:`bgRun` 并汇总进度；支持 ``stop()``
    优雅停止（不再启动新任务并终止正在运行的子进程）。
    """

    finished = pyqtSignal(str)
    updated = pyqtSignal(int)

    def __init__(self, cmdList=None, parent=None, max_thread=None):
        super().__init__(parent)
        self.cmd_list = list(cmdList or [])
        # 外层并发样本数：优先用调用方传入的值，否则取默认（env 可覆盖，见 default_parallel）。
        self.max_thread = int(max_thread) if max_thread else default_parallel()
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        total = len(self.cmd_list)
        if total == 0:
            self.finished.emit("")
            return

        workers = []      # 当前在运行的 bgRun 列表
        next_index = 0    # 下一个待启动的命令下标
        done = 0          # 已完成的任务数
        emitted = 0       # 已通过 updated 上报的完成数

        while not self._stop:
            # 扫描并移除已结束的 worker
            for worker in list(workers):
                if worker.isFinished():
                    workers.remove(worker)
                    done += 1

            # 启动新任务直到达到并发上限
            while not self._stop and next_index < total and len(workers) < self.max_thread:
                worker = bgRun(self.cmd_list[next_index])
                next_index += 1
                worker.start()
                workers.append(worker)

            # 上报进度增量
            if done > emitted:
                self.updated.emit(done - emitted)
                emitted = done

            if not workers and next_index >= total:
                break
            self.msleep(200)

        # 停止前终止仍在运行的子进程，避免残留
        for worker in workers:
            worker.stop()
            worker.wait(2000)

        if not self._stop:
            self.finished.emit("")


class bcl2fastqThread(QThread):
    """运行 bcl2fastq 拆分脚本（``bash ./.run.sh``），并返回日志最后一行。"""

    finished = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._proc = None

    def stop(self):
        _kill_process_group(self._proc)

    def bcl2fastq(self):
        log_path = "/tmp/bcl2fastq_" + str(time.time())
        with open(log_path, "w") as log_file:
            self._proc = subprocess.Popen(
                ["bash", "./.run.sh"],
                stderr=log_file,
                start_new_session=True,
            )
            self._proc.wait()

        log = ""
        try:
            with open(log_path, "r") as f:
                log = f.read()
        except OSError as e:  # noqa: BLE001
            print(e)

        if log:
            return log.split("]")[-1]
        return ""

    def run(self):
        log_last = self.bcl2fastq()
        time.sleep(3)
        self.finished.emit(log_last)


class lyricThread(QThread):
    """每 10 分钟刷新一次「今日诗词」文案。"""

    updated = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        while not self._stop:
            # 以 1 秒为粒度睡眠，便于及时响应停止请求。
            for _ in range(600):
                if self._stop:
                    return
                self.msleep(1000)
            self.updated.emit(getLyric())


if __name__ == "__main__":
    # 简单的自检：生成若干任务并观察调度。
    class _Demo(QThread):
        def __init__(self):
            super().__init__()
            self.jobs = bgCRISPResso2(cmdList=["echo a", "echo b", "echo c"])

    print("background_task 模块自检完成")
