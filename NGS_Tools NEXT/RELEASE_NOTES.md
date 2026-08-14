# NGS_Tools v1.7.0

> 这是一次大规模重构与稳定性优化版本：保留原有 PyQt5 中文界面与全部功能行为不变，同时消除大量重复代码、修复多处真实 Bug、并把这一路上遇到的环境/打包问题一次性解决。

## ✨ Highlights

- 新增公共模块 `common.py`，五个 GUI 模块代码量**减少约一半**，只保留各自的分析逻辑。
- 修复 `addLine` 越界、`delLine` 重复删行、汇总结果列名错误等多个会影响实际结果的 Bug。
- 环境一键安装（`checkEnv.py`）重写，适配 2024 年之后的 conda 生态变化（清华镜像下线、`defaults` 要求 ToS、mamba 故障等）。
- CRISPResso 分析的**外层并发与内层线程数可在界面调整并自动记忆**，避免按 CPU 核数盲目并发导致的内存溢出，同时提高吞吐。
- 新增 PyInstaller 打包配置与构建脚本，支持一键打包为 Ubuntu 可执行程序。

## 🐛 Bug Fixes

| 位置 | 原问题 | 修复 |
| --- | --- | --- |
| `addLine` | `new_row = current_count + 1` 越界、硬编码 8 列，新增行填不上内容 | 按实际列数在正确行追加 |
| `delLine` | 循环里反复删除 `selection[0]` 同一行 | 从后往前按索引逐行删除 |
| `NHEJ.summarize` | 写入结果表中不存在的列 `正确编辑占总体的比例` | 改为正确的 `NHEJ占总体的比例` |
| `HDR_PE.summarize` | `n_deleted + n_deleted` 重复相加 | 改为 `n_inserted + n_deleted` |
| `BE.summarize` | 非特异编辑率分母误用上一表格的 `allReads` | 改为 `allSubReads` |
| `demultiplex` | 拆分脚本 `%d` 应为 `${d}`；索引位置写死 `"10"`；单文件时 `seqPair[1]` 越界 | 全部修复，索引位置改读界面输入 |
| `NGS_Tools.checkUpdate` | `self = QMessageBox...` 重绑定 + 裸 `app.exec_()`（会 NameError） | 修复 |
| `centerWin` | 弃用的 `QDesktopWidget` + 随机偏移可能移出屏幕 | 改用 `QScreen` 精确居中 |
| 汇总解析 | 除零未保护 | 增加 `allReads == 0` 等除零保护 |

## 🔧 Refactoring

- 新增 `common.py`：集中 `reverseDNA` / `getLyric` / `TableWindowMixin` / conda 配置 / 环境探测 / 子进程工具。
- 五个 GUI 模块统一继承 `TableWindowMixin`，删除约 500 行复制粘贴的表格/文件操作代码。
- 「今日诗词」彩蛋去重并改为可开关：设置环境变量 `NGS_TOOLS_LYRIC=0` 关闭。

## ⚡ Robustness & Thread Safety

- 重写 `background_task.py`：移除 `locals()["task_"+str(i)]` 动态变量名（会 KeyError），改为清晰的并发调度器。
- 所有 `os.system` / `os.popen` 替换为 `subprocess`（`shlex.split` 防 shell 注入、`start_new_session` 支持整组终止）。
- 弃用 `QThread.terminate()`，改为 `stop()` 优雅停止；新增 `_summarized` 防重复汇总。
- 窗口启动时的版本探测改为后台 `ToolDetector` 线程，不再阻塞界面。
- `openFolder` 由仅支持 GNOME 的 `nautilus` 改为 `QDesktopServices`，跨桌面环境可用。
- 安装失败不再导致程序闪退，改为弹出友好提示框。
- 拖拽路径解析改用 `urllib.parse.unquote`。

## 🚀 Performance & Memory

- 外层并发不再等于 CPU 核数（原版在 24 核机器上会同时开 24 个 CRISPResso 进程，极易 OOM），默认改为 `min(CPU核数, 8)`。
- BE / HDR-PE / NHEJ 窗口新增「并发样本数（外层）」与「每样本线程数（内层 -p）」两个可调项，并**自动保存到 `~/.NGS_Tools/config.json`**，下次启动恢复。
- 去掉 `conda run` 的启动开销，直接调用 `~/miniconda3/envs/NGS/bin/CRISPResso` 并注入 PATH，每个样本省约 1~2 秒。
- 界面提示「外层 × 内层 ≈ 总线程数，建议不超过 CPU 逻辑核数（虚拟机里即 vCPU 数）」，避免过度订阅反而变慢。
- 支持环境变量预设：`NGS_MAX_PARALLEL`（外层）、`NGS_CRISPRESSO_PROCESSES`（内层 -p）。

## 🌍 环境安装（conda）修复

适配 2024 年后 conda 生态的若干变化：

- 清华大学镜像站已下线 Anaconda 镜像 → 镜像地址改为**可配置**（默认 SJTUG，`CONDA_MIRROR` 常量可换阿里云/官方）。
- Anaconda 官方 `defaults` 源要求接受商业条款（ToS）→ **彻底移除 `defaults`**，仅使用 conda-forge + bioconda。
- 国内直连 conda 官方源不稳定 → 通过 `custom_channels` 走国内镜像。
- standalone `mamba` 在部分环境出现 `ZSTD decompression error` / `Download error (23)` → **全程改用 `conda`**（现代 conda 已内置 libmamba 求解器，速度相当）。
- bioconda 索引体积大，不再放入默认 channels，仅在安装 CRISPResso2 时用 `-c bioconda` 临时指定。
- CRISPResso 探测误判 → 改用 `--help` 返回码判断，版本号 stdout/stderr 一起检查。

## 📦 Packaging

- 新增 `NGS_Tools.spec`：PyInstaller 打包配置，显式收集 `openpyxl` 与 `qdarktheme` 资源。
- 新增 `packaging/build_ubuntu.sh`：一键构建脚本，产出 `dist/NGS_Tools-ubuntu-x86_64.tar.gz`。
- 新增 `packaging/NGS_Tools.desktop`：桌面快捷方式模板。
- `requirements.txt` 调整：`pyqtdarktheme` 改为可选依赖，兼容 Python 3.13。

## ✅ Compatibility

- `qdarktheme` 改为可选导入：在 Python 3.13（新版 Ubuntu 默认）下无法安装时自动退回系统默认主题，不再报 `AttributeError: enable_hi_dpi`。
- 支持在 Python 3.10–3.13 下运行；如需暗色主题，请在 Python 3.10/3.11/3.12 环境构建。

## 📚 Docs

- `README.md` 新增「打包为 Ubuntu 可执行程序」与「配置项」章节。

---

## 🙏 Notes

- 本版本**保留原有 PyQt5 + 中文界面 + 全部功能行为**，`.ui` 文件与生成的 `gui_*.py` 未做改动。
- 原始源码仍可在 `NGS_Tools-master.backup-original` 中对照查看。

**Full Changelog**: 重构去重 + Bug 修复 + 健壮性/线程安全改进 + 性能/内存优化 + 环境安装与打包适配
