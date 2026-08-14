#!/usr/bin/env bash
# 在 Ubuntu（推荐 22.04，x86_64）上构建 NGS_Tools 独立可执行程序。
# 用法：bash packaging/build_ubuntu.sh
set -euo pipefail

# 切到项目根目录（脚本所在目录的上一级）
cd "$(dirname "$0")/.."

echo "==> 创建构建用虚拟环境并安装依赖"
python3 -m venv .venv-build
# shellcheck disable=SC1091
source .venv-build/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "==> 开始 PyInstaller 打包（onedir）"
python -m PyInstaller --noconfirm --clean NGS_Tools.spec

echo "==> 打包为 tar.gz 便于分发"
tar -czf "dist/NGS_Tools-ubuntu-x86_64.tar.gz" -C dist NGS_Tools

echo "==> 完成，产物："
ls -lh dist/
echo ""
echo "运行方式：解压 dist/NGS_Tools-ubuntu-x86_64.tar.gz，"
echo "然后在可写目录下执行 ./NGS_Tools（首次运行点界面里的安装按钮补装 conda 环境）。"
