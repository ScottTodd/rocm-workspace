from __future__ import annotations

import concurrent.futures
import ctypes
from ctypes import wintypes
from pathlib import Path
import subprocess
import sys
import tempfile


def run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True)


def open_exclusive(path: Path):
    create_file = ctypes.windll.kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    handle = create_file(
        str(path),
        0xC0000000,  # GENERIC_READ | GENERIC_WRITE
        0,  # No sharing: block a second writer or metadata update.
        None,
        3,  # OPEN_EXISTING
        0x80,  # FILE_ATTRIBUTE_NORMAL
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError()
    return handle


def report(label: str, result: subprocess.CompletedProcess[str]):
    print(f"{label}: rc={result.returncode}")
    print(f"{label}: stdout={result.stdout!r}")
    print(f"{label}: stderr={result.stderr!r}")


def main() -> int:
    cmake = sys.argv[1]
    source_dir = Path(sys.argv[2])
    ninja = sys.argv[3]
    scratch = Path(sys.argv[4])
    scratch.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=scratch, prefix="issue5024-touch-") as temp:
        root = Path(temp)
        stamp = root / "shared.stamp"
        stamp.write_text("stamp", encoding="utf-8")

        commands = [[cmake, "-E", "touch", str(stamp)] for _ in range(1600)]
        with concurrent.futures.ThreadPoolExecutor(max_workers=32) as executor:
            results = list(executor.map(run, commands))
        failures = [result for result in results if result.returncode]
        print(f"concurrent_touches={len(results)} failures={len(failures)}")
        if failures:
            report("first concurrent failure", failures[0])

        handle = open_exclusive(stamp)
        try:
            report("direct locked touch", run([cmake, "-E", "touch", str(stamp)]))
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

        build_dir = root / "build"
        configure = run(
            [
                cmake,
                "-S",
                str(source_dir),
                "-B",
                str(build_dir),
                "-G",
                "Ninja",
                f"-DCMAKE_MAKE_PROGRAM={ninja}",
                f"-DLOCKED_FILE={stamp}",
            ]
        )
        report("configure", configure)
        if configure.returncode:
            return configure.returncode

        handle = open_exclusive(stamp)
        try:
            report("ninja locked touch", run([cmake, "--build", str(build_dir)]))
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
