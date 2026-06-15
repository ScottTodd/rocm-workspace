# PR Review: ROCm/TheRock#2705

* **PR:** https://github.com/ROCm/TheRock/pull/2705
* **Title:** Refactor GPU selection flags for Pytorch unit/smoke test runners
* **Author:** `sstamenk`
* **Reviewed:** 2026-06-01
* **Head:** `5d80c51895778b7d4b7a7f56c7dfe0e28603839f`
* **Base:** `main`
* **Net changes:** +264 / -131 across 7 files

---

## Summary

This PR splits PyTorch GPU selection into a discovery stage (`--device-query`) and
a visibility stage (`--gpu-policy`), wires those options into the PyTorch wheel
test workflows, updates the unit/full/smoke runners, and documents the new modes.

CI evidence checked:

- `pre-commit` passed.
- Linux and Windows unit tests passed.
- Current overall CI is failing in the foundation stage at `Configure AWS credentials for artifact uploads`; the failed jobs are from a fork run with `Secret source: None`, and the build/test steps before artifact upload completed. I did not treat this as evidence of a PyTorch runner regression.
- The PR description links targeted PyTorch wheel workflow runs and local GPU-selection logs.

---

## Overall Assessment

**CHANGES REQUESTED** - one ordering bug remains in the central GPU-selection path.

---

## Detailed Findings

### BLOCKING: `policy="all"` can reorder interleaved GPUs

The PR says device order is preserved, but the current representation cannot
preserve visible order when the same architecture appears in multiple
non-contiguous positions. `get_all_supported_devices()` groups results into
`dict[str, list[int]]` by architecture, then `set_gpu_execution_policy()` flattens
that grouped dictionary by architecture order:

- [`pytorch_utils.py` lines 222-227](https://github.com/ROCm/TheRock/blob/5d80c51895778b7d4b7a7f56c7dfe0e28603839f/external-builds/pytorch/pytorch_utils.py#L222-L227)
- [`pytorch_utils.py` lines 314-320](https://github.com/ROCm/TheRock/blob/5d80c51895778b7d4b7a7f56c7dfe0e28603839f/external-builds/pytorch/pytorch_utils.py#L314-L320)

For a visible order like:

```text
0:gfx1200, 1:gfx1201, 2:gfx1200
```

the device map becomes:

```python
{"gfx1200": [0, 2], "gfx1201": [1]}
```

and `policy="all"` emits `HIP_VISIBLE_DEVICES=0,2,1` instead of `0,1,2`. That
changes PyTorch logical device ordering for multi-GPU tests. This path is not
just manual: `run_pytorch_tests_full.py` resolves distributed `auto` defaults to
`device_query="all"` and `gpu_policy="all"`:

- [`run_pytorch_tests_full.py` lines 364-371](https://github.com/ROCm/TheRock/blob/5d80c51895778b7d4b7a7f56c7dfe0e28603839f/external-builds/pytorch/run_pytorch_tests_full.py#L364-L371)

The PR discussion already contains a simulated wildcard example with visible
`gfx942, gfx1200, gfx1201, gfx1200` where the selected device list is logged as
`1, 3, 2`, which demonstrates the same reorder.

**Required action:** carry an ordered list of `(arch, device_index)` pairs from
the discovery step through policy application, or otherwise preserve the original
logical order explicitly. Add a regression test for an interleaved repeated-arch
topology, including a pre-set `HIP_VISIBLE_DEVICES` order.

### IMPORTANT: GPU-selection tests are not committed

The PR description links manual/simulated validation, but no automated tests were
added for the new selection contract. This logic is testable without GPU
hardware by stubbing `get_supported_and_visible_gpus()` and controlling
`HIP_VISIBLE_DEVICES`, and the bug above is exactly the kind of regression such a
test would catch.

**Recommendation:** add focused unit tests for `get_all_supported_devices()`,
`get_unique_supported_devices()`, `set_gpu_execution_policy()`, and
`configure_gpu_visibility()` covering:

- visible-order preservation with interleaved architectures,
- pre-set `HIP_VISIBLE_DEVICES`,
- wildcard/specific family filters,
- `unique/single`, `unique/all`, `all/single`, and `all/all`.

---

## Conclusion

**Approval Status: CHANGES REQUESTED**

Fix the ordering representation for the `all` policy and commit regression tests
for the GPU-selection matrix before merge.

Generated with Codex.
