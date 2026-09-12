# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for the STFC Tactical Advisor desktop build.
#
# Build (on the TARGET OS — PyInstaller does not cross-compile):
#   pyinstaller stfc_advisor.spec
#
# Produces dist/STFC-Advisor/ — hand the whole folder to the user; they
# launch it via STFC-Advisor.exe inside it. See packaging/BUILD_WINDOWS.md.

from PyInstaller.utils.hooks import collect_submodules

datas = [
    ("web", "web"),
    ("data", "data"),
    ("profiles/player_profile.template.json", "profiles"),
    ("profiles/player_profile.schema.json", "profiles"),
]
hiddenimports = []

hiddenimports += collect_submodules("uvicorn")
hiddenimports += ["pystray._win32"]

a = Analysis(
    ["run_app.py"],
    pathex=["."],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="STFC-Advisor",
    console=False,
    icon="web/desktop-icon.ico",
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    name="STFC-Advisor",
)
