# -*- coding: utf-8 -*-
"""一键安装分析环境：miniconda + bcl2fastq + CRISPResso2。

说明：全程使用 ``conda``（而非独立的 ``mamba`` 程序）。现代 conda（>= 23）
已内置 libmamba 求解器，速度与 mamba 相当，且避免独立 mamba 在部分环境下
出现 ``ZSTD decompression error`` / ``Download error (23)`` 等故障。
"""

import os
import subprocess
import tempfile

from common import CONDA_ENV, CONDA_EXE, conda_run_args

# 国内 conda 镜像基地址（清华镜像已于 2024 年下线）。
# 可改成其它可用镜像，例如：
#   - https://mirrors.sjtug.sjtu.edu.cn/anaconda   （上海交大，推荐）
#   - https://mirrors.aliyun.com/anaconda           （阿里云）
# 留空字符串 "" 表示使用 conda 官方源（适合能直连 anaconda.org 的网络）。
CONDA_MIRROR = "https://mirrors.sjtug.sjtu.edu.cn/anaconda"


def _run(args, check=True):
    """运行命令并返回 CompletedProcess（输出直接显示在终端）。"""
    return subprocess.run(args, check=check)


def _capture(args, timeout=120):
    """运行命令并返回 stdout / stderr 文本。"""
    proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    return proc.stdout or "", proc.stderr or ""


def checkConda():
    """确保 miniconda 与 ``NGS`` 环境存在。"""
    stdout, _ = _capture([CONDA_EXE, "info"])
    if "conda version" not in stdout:
        installer = os.path.join(tempfile.gettempdir(), "install_miniconda.sh")
        with open(installer, "w") as f:
            f.write(
                "#!/bin/bash\n"
                "mkdir -p ~/miniconda3\n"
                "wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh "
                "-O ~/miniconda3/miniconda.sh\n"
                "bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3\n"
                "rm -rf ~/miniconda3/miniconda.sh\n"
                "~/miniconda3/bin/conda init bash\n"
            )
        _run(["bash", installer])
        os.remove(installer)

    _, env_stdout = _capture([CONDA_EXE, "env", "list"])
    if CONDA_ENV not in env_stdout:
        _run([CONDA_EXE, "create", "-n", CONDA_ENV, "-c", "conda-forge", "python=3.9", "-y"])


def resetCondaMirror():
    """重写 .condarc：只用 conda-forge，并可选走国内镜像。

    原因：
    1) 清华镜像站已于 2024 年下线 Anaconda 镜像；
    2) Anaconda 官方 ``defaults`` 源（repo.anaconda.com）要求接受商业条款（ToS），
       报 ``CondaToSNonInteractiveError``；
    3) 国内直连 conda 官方源（anaconda.org）经常超时，需要走国内镜像。
    因此这里显式写入不含 ``defaults`` 的配置，并把 conda-forge/bioconda 指向
    :data:`CONDA_MIRROR` 指定的镜像。bioconda 的索引很大，不放进默认 channels，
    只在装 CRISPResso2 时用 ``-c bioconda`` 临时指定。
    """
    condarc = os.path.join(os.path.expanduser("~"), ".condarc")
    if CONDA_MIRROR:
        content = (
            "channels:\n"
            "  - conda-forge\n"
            "show_channel_urls: true\n"
            "custom_channels:\n"
            "  conda-forge: %s/cloud\n"
            "  bioconda: %s/cloud\n" % (CONDA_MIRROR, CONDA_MIRROR)
        )
    else:
        content = (
            "channels:\n"
            "  - conda-forge\n"
            "show_channel_urls: true\n"
        )
    with open(condarc, "w") as f:
        f.write(content)
    _run([CONDA_EXE, "clean", "-i", "-y"], check=False)


def checkBCL2Fq():
    """确保 bcl2fastq 已安装（来自 dranew 社区频道）。"""
    _, stderr = _capture(conda_run_args("bcl2fastq", "-v"))
    if "Illumina" in stderr:
        print("### bcl2fastq ready ###")
        return stderr

    print("未安装bcl2fastq")
    print("开始安装")
    _run([CONDA_EXE, "install", "-n", CONDA_ENV, "-c", "dranew", "-c", "conda-forge", "bcl2fastq", "-y"])


def checkCRISPResso2():
    """确保 CRISPResso2 已安装（来自 bioconda 频道）。"""
    proc = _run(conda_run_args("CRISPResso", "--help"), check=False)
    if proc.returncode == 0:
        print("### CRISPResso ready ###")
        return 0

    print("未安装CRISPResso")
    print("开始安装")
    _run([CONDA_EXE, "install", "-n", CONDA_ENV, "-c", "bioconda", "-c", "conda-forge", "CRISPResso2", "-y"])


def check():
    resetCondaMirror()
    checkConda()
    checkBCL2Fq()
    checkCRISPResso2()


if __name__ == "__main__":
    check()
