"""Run a child after temporarily setting the inherited Windows DLL directory."""

import argparse
import ctypes
import os
from pathlib import Path
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Set the process DLL directory, run a child, and restore the default."
        )
    )
    parser.add_argument("dll_directory", help="Directory containing runtime DLLs")
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="Child command, optionally preceded by --",
    )
    args = parser.parse_args()

    if os.name != "nt":
        raise OSError("This probe requires Windows")

    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("a child command is required")

    dll_directory = Path(args.dll_directory).resolve(strict=True)
    if not dll_directory.is_dir():
        raise NotADirectoryError(dll_directory)

    # WinDLL("kernel32") creates a ctypes interface to Windows' Kernel32 API.
    # use_last_error=True lets ctypes preserve the calling thread's Win32 error
    # code so a failed BOOL result can be converted into a useful exception.
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    set_dll_directory = kernel32.SetDllDirectoryW
    set_dll_directory.argtypes = [ctypes.c_wchar_p]
    set_dll_directory.restype = ctypes.c_bool

    if not set_dll_directory(str(dll_directory)):
        raise ctypes.WinError(ctypes.get_last_error())

    try:
        # SetDllDirectory state is inherited by a newly created child process.
        # Run sequentially because the setting is process-global in this parent.
        subprocess.run(command, check=True)
    finally:
        # NULL restores the standard DLL search order for later work in this
        # long-lived parent, even if launching or running the child failed.
        if not set_dll_directory(None):
            raise ctypes.WinError(ctypes.get_last_error())


if __name__ == "__main__":
    main()
