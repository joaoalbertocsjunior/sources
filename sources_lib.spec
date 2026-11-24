# PyInstaller spec for sources-lib standalone binary.
# Bundles CPython + all stdlib-only adapters; optional extras (litellm, mcp,
# PyGithub, httpx) are included only when present in the build environment.
# To build locally: pip install ".[all]" pyinstaller && pyinstaller sources_lib.spec

from PyInstaller.utils.hooks import collect_submodules, collect_data_files

hiddenimports = collect_submodules("sources_lib")

# Pull in optional extras if installed
for pkg in ("litellm", "mcp", "github", "httpx", "psycopg2"):
    try:
        __import__(pkg)
        hiddenimports += collect_submodules(pkg)
    except ImportError:
        pass

datas = collect_data_files("sources_lib")

a = Analysis(
    ["src/sources_lib/__main__.py"],
    pathex=["src"],
    binaries=[],
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
    a.binaries,
    a.datas,
    [],
    name="sources-lib",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
