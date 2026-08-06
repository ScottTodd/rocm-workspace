# Windows DLL Search Probes

These probes demonstrate loader selection without modifying the ROCm
installation. They require Windows and use only the Python standard library.

## Report the module selected by ordinary search

```powershell
python .\report_loaded_module.py OpenCL.dll
```

The probe calls `ctypes.WinDLL()` with a basename, then asks
`GetModuleFileNameW()` for the full path of the loaded module. Using a basename
is important: passing an absolute DLL path would bypass the search-order
question being tested.

## Run a child with an inherited DLL directory

```powershell
python .\run_child_with_dll_directory.py `
  D:\path\to\rocm\bin `
  -- python .\report_loaded_module.py OpenCL.dll
```

The launcher calls `SetDllDirectoryW()` in the parent, launches the child, then
restores the parent's normal state in a `finally` block. This is the same shape
recommended for the single-threaded hipthreads example runner.

Run `report_loaded_module.py` once directly, once through the launcher, and once
directly again. On a machine with same-named copies in `System32` and the chosen
ROCm `bin`, the three paths demonstrate ordinary selection, the inherited
override, and successful restoration.

## Limitations

- This proves selection for the named DLL; it does not enumerate the complete
  runtime closure.
- Loading an arbitrary library can execute its initialization code. Use trusted
  artifacts only.
- `SetDllDirectoryW` is process-global. Do not change it concurrently with
  unrelated loads or child launches in the same parent.
- The child executable is not made self-contained. Direct launch outside this
  parent still follows its ordinary loader contract.

---

Prepared with OpenAI Codex.
