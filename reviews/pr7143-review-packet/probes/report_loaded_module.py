"""Load one Windows DLL by basename and report the selected module path."""

import argparse
import ctypes
import os
from ctypes import wintypes


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Load a Windows DLL and print the path selected by the loader."
    )
    parser.add_argument(
        "dll_name",
        help="DLL basename to load, for example OpenCL.dll or amdhip64_7.dll",
    )
    args = parser.parse_args()

    if os.name != "nt":
        raise OSError("This probe requires Windows")

    # WinDLL loads the named module using normal Windows loader semantics and
    # returns an object whose _handle is the native HMODULE.
    module = ctypes.WinDLL(args.dll_name)

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_module_file_name = kernel32.GetModuleFileNameW
    get_module_file_name.argtypes = [wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    get_module_file_name.restype = wintypes.DWORD

    buffer = ctypes.create_unicode_buffer(32768)
    length = get_module_file_name(module._handle, buffer, len(buffer))
    if length == 0:
        error = ctypes.get_last_error()
        raise ctypes.WinError(error)
    if length == len(buffer):
        raise RuntimeError("Resolved module path exceeded the probe buffer")

    print(buffer.value)


if __name__ == "__main__":
    main()
