# NGS 小工具箱

> 本仓库来源自 [Masterchiefm/NGS_Tools](https://github.com/Masterchiefm/NGS_Tools)，
> 在原作者莫淇钦（上海科技大学马涵慧实验室）的基础上进行了代码重构、Bug 修复、遵循原项目许可开源。具体更新内容见release页面。

## 目的
提供图形界面，让不会命令行的人也可以使用生信工具简便地分析基因编辑效果。

## 功能
1. 提供图形化的bcl2fastq界面，可以拆分下机数据（demultiplex）。
详细说明请查阅[illumina说明](https://support.illumina.com/sequencing/sequencing_software/bcl2fastq-conversion-software.html)
2. 提供[CRISPResso2](https://github.com/pinellolab/CRISPResso2)
的图形操作界面，可以批量分析HDR，PE，BE，NHEJ.
3. 收集编辑数据，并汇总到excel表。
4. 一键安装分析环境

# 打包为 Ubuntu 可执行程序（可选）
在必须在 Linux 上构建，且建议构建机与运行机系统版本一致：

```
bash packaging/build_ubuntu.sh
```

脚本会创建虚拟环境、安装依赖并用 PyInstaller 打包，产物在 `dist/NGS_Tools-ubuntu-x86_64.tar.gz`。


# 配置项（可选）
标签栏的「今日诗词」彩蛋默认开启。若不需要联网获取诗词，可在启动前设置环境变量关闭：

```
# Linux / macOS / WSL
export NGS_TOOLS_LYRIC=0
```

关闭后标签栏将只显示静态说明文字，不再发起外部网络请求。

CRISPResso 分析的并发与线程数可在 BE / HDR-PE / NHEJ 窗口界面直接调整，并会自动记住上次设置
（保存到 `~/.NGS_Tools/config.json`）：

- 并发样本数（外层进程）
- 每样本线程数（内层 -p）

也可通过环境变量预设默认值（仅首次、或清空配置文件后生效）：

```
# 外层并发样本数（默认 min(CPU核数, 8)）
export NGS_MAX_PARALLEL=8

# 每个 CRISPResso 进程内部线程数 -p（默认 3，设为 1 可关闭）
export NGS_CRISPRESSO_PROCESSES=3
```

建议：**外层并发 × 内层线程 ≈ 总线程数，最好不要超过 CPU 逻辑核数**（在虚拟机里即 vCPU 数），
否则进程间互相争抢反而更慢。总内存 ≈ 外层并发 × 单样本内存，32GB 内存建议外层并发 6~8。

