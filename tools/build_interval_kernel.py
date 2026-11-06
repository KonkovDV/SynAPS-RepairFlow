"""Compile the oracle interval kernel with rustc. No crates.io dependency."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "native" / "interval_kernel.rs"


def output_path() -> Path:
    native = ROOT / "native"
    if sys.platform == "win32":
        return native / "interval_kernel.dll"
    if sys.platform == "darwin":
        return native / "libinterval_kernel.dylib"
    return native / "libinterval_kernel.so"


def build() -> Path:
    compiler = shutil.which("rustc")
    if compiler is None:
        raise SystemExit("rustc is not on PATH")
    target = output_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [compiler, "--crate-type", "cdylib", "-O", "-o", str(target), str(SOURCE)],
        check=True,
    )
    return target


if __name__ == "__main__":
    print(build())
