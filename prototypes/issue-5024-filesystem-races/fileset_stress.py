#!/usr/bin/env python
"""Stress fileset_tool.py artifact-flatten concurrency for TheRock issue #5024."""

from __future__ import annotations

import argparse
import collections
import concurrent.futures
import ctypes
from ctypes import wintypes
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import time


def make_artifacts(root: Path, workers: int, files: int, overlap: bool) -> list[Path]:
    artifacts = []
    for worker in range(workers):
        artifact = root / f"artifact-{worker}"
        basedir = artifact / "component" / "stage"
        (basedir / "bin").mkdir(parents=True)
        (artifact / "artifact_manifest.txt").write_text(
            "component/stage\n", encoding="utf-8"
        )
        for file_index in range(files):
            if overlap:
                name = f"file-{file_index:04}.dat"
            else:
                name = f"worker-{worker:02}-file-{file_index:04}.dat"
            (basedir / "bin" / name).write_bytes(
                (f"worker={worker};file={file_index}\n" * 8).encode()
            )
        artifacts.append(artifact)
    return artifacts


def invoke(python: Path, tool: Path, artifact: Path, output: Path):
    return subprocess.run(
        [
            str(python),
            str(tool),
            "artifact-flatten",
            "-o",
            str(output),
            str(artifact),
        ],
        text=True,
        capture_output=True,
    )


def invoke_copy(python: Path, tool: Path, source: Path, output: Path):
    return subprocess.run(
        [str(python), str(tool), "copy", str(output), str(source)],
        text=True,
        capture_output=True,
    )


def hold_without_delete_sharing(path: Path, ready: threading.Event, stop: threading.Event):
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
        0x80000000,  # GENERIC_READ
        0x00000001,  # FILE_SHARE_READ (deliberately omit write/delete sharing)
        None,
        3,  # OPEN_EXISTING
        0x80,  # FILE_ATTRIBUTE_NORMAL
        None,
    )
    if handle == wintypes.HANDLE(-1).value:
        raise ctypes.WinError()
    ready.set()
    try:
        stop.wait()
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--tool", type=Path, required=True)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=100)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--files", type=int, default=32)
    parser.add_argument(
        "--operation", choices=("flatten", "copy-common"), default="flatten"
    )
    parser.add_argument("--overlap", action="store_true")
    parser.add_argument("--lock-target", action="store_true")
    args = parser.parse_args()

    args.scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=args.scratch, prefix="issue5024-") as temp:
        root = Path(temp)
        artifacts = make_artifacts(root, args.workers, args.files, args.overlap)
        common_source = artifacts[0] / "component" / "stage"
        output = root / "dist-rocm"
        failures = []
        return_codes = collections.Counter()

        for round_index in range(args.rounds):
            if output.exists():
                shutil.rmtree(output)

            lock_thread = None
            lock_stop = threading.Event()
            if args.lock_target:
                if args.operation != "flatten":
                    raise ValueError("--lock-target is only implemented for flatten")
                seed = invoke(args.python, args.tool, artifacts[0], output)
                if seed.returncode:
                    print(seed.stderr, file=sys.stderr)
                    return seed.returncode
                locked_name = (
                    "file-0000.dat"
                    if args.overlap
                    else "worker-00-file-0000.dat"
                )
                ready = threading.Event()
                lock_thread = threading.Thread(
                    target=hold_without_delete_sharing,
                    args=(output / "bin" / locked_name, ready, lock_stop),
                    daemon=True,
                )
                lock_thread.start()
                if not ready.wait(5):
                    raise RuntimeError("Timed out opening locked target")

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=args.workers
            ) as executor:
                if args.operation == "flatten":
                    futures = [
                        executor.submit(
                            invoke, args.python, args.tool, artifact, output
                        )
                        for artifact in artifacts
                    ]
                else:
                    futures = [
                        executor.submit(
                            invoke_copy,
                            args.python,
                            args.tool,
                            common_source,
                            output / f"worker-{worker}",
                        )
                        for worker in range(args.workers)
                    ]
                results = [future.result() for future in futures]

            lock_stop.set()
            if lock_thread:
                lock_thread.join()

            for worker, result in enumerate(results):
                return_codes[result.returncode] += 1
                if result.returncode:
                    failures.append((round_index, worker, result))
            if (round_index + 1) % 10 == 0:
                print(
                    f"rounds={round_index + 1} invocations={(round_index + 1) * args.workers} "
                    f"failures={len(failures)}",
                    flush=True,
                )

        print(f"return_codes={dict(return_codes)}")
        print(f"failures={len(failures)}")
        for round_index, worker, result in failures[:5]:
            print(f"--- round={round_index} worker={worker} rc={result.returncode}")
            print(result.stdout.rstrip())
            print(result.stderr.rstrip())
        return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
