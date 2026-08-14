# -*- mode: python ; coding: utf-8 -*-
# PyInstaller 打包配置（onedir 模式，产物在 dist/NGS_Tools/）。
# 构建命令：pyinstaller --noconfirm --clean NGS_Tools.spec
#
# 注意：必须在 Linux x86_64 上构建（推荐与目标机器相同的 Ubuntu 版本，
# 例如都在 Ubuntu 22.04 上构建/运行，避免 glibc 版本不兼容）。

from PyInstaller.utils.hooks import collect_all

datas = []
binaries = []
hiddenimports = [
    # pandas 读写 .xlsx 时通过 importlib 动态加载 openpyxl，需显式声明
    "openpyxl",
]

# qdarktheme 是可选依赖：已安装时才收集其主题 qss 资源（Python 3.12+ 上通常未安装）
try:
    import qdarktheme  # noqa: F401
    q_datas, q_bins, q_hidden = collect_all("qdarktheme")
    datas += q_datas
    binaries += q_bins
    hiddenimports += q_hidden
except ImportError:
    pass

a = Analysis(
    ["NGS_Tools.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="NGS_Tools",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,           # 保留 stdout/stderr：程序大量使用 print 且需向 conda 子进程传递标准流
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="NGS_Tools",
)
