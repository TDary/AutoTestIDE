# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

# Project root — spec file is in the project root
ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "src" / "autotest_ide" / "app.py")],
    pathex=[str(ROOT / "src")],
    binaries=[],
    datas=[
        # Report templates — bundled so Jinja2 can find them at runtime
        (str(ROOT / "src" / "autotest_ide" / "report" / "template.html"), "autotest_ide/report"),
        (str(ROOT / "src" / "autotest_ide" / "report" / "report.css"), "autotest_ide/report"),
        (str(ROOT / "src" / "autotest_ide" / "report" / "report.js"), "autotest_ide/report"),
        # Runner script — bundled as a standalone script for subprocess spawn
        (str(ROOT / "src" / "autotest_ide" / "runner" / "runtest.py"), "scripts"),
        # SDK adapters — need __init__.py files for package discovery
        (str(ROOT / "src" / "autotest_ide" / "sdks"), "autotest_ide/sdks"),
    ],
    hiddenimports=[
        "autotest_ide",
        "autotest_ide.app",
        "autotest_ide.core.log",
        "autotest_ide.core.errors",
        "autotest_ide.core.protocol",
        "autotest_ide.core.protocol_base",
        "autotest_ide.core.protocol_poco",
        "autotest_ide.core.poco_client",
        "autotest_ide.core.forwarder",
        "autotest_ide.core.device",
        "autotest_ide.core.device_manager",
        "autotest_ide.core.locator",
        "autotest_ide.core.report_model",
        "autotest_ide.ui.main_window",
        "autotest_ide.ui.device_panel",
        "autotest_ide.ui.editor",
        "autotest_ide.ui.tree_panel",
        "autotest_ide.ui.property_panel",
        "autotest_ide.ui.console",
        "autotest_ide.ui.threads",
        "autotest_ide.ui.run_controller",
        "autotest_ide.ui.report_view",
        "autotest_ide.ui.icons",
        "autotest_ide.ui.style",
        "autotest_ide.runner.reporter",
        "autotest_ide.runner.recorder",
        "autotest_ide.runner.runtime",
        "autotest_ide.report",
        "autotest_ide.sdks",
        "autotest_ide.sdks.poco",
        "autotest_ide.sdks.jx4",
        "autotest_ide.sdks.jx4.protocol",
        "PyQt5.QtWebEngineWidgets",
        "PyQt5.QtSvg",
        "psutil",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "PIL", "cv2"],
    noarchive=False,
    optimize=0,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AutoTest IDE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,  # No terminal window
    icon=None,  # Add .ico later if desired
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AutoTest IDE",
)
