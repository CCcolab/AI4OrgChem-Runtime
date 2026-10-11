[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/NATIVE_WSL2_RUNTIME_zh-CN.md)

# Ordinary WSL2: read-only environment Check

`scripts/check-wsl2-runtime.py` checks a specified WSL2 distribution and Python environment. It reads standard-library/platform information, package metadata, `/proc`, cgroup counters and explicitly selected source-file hashes. It does not import original research scripts or scientific PySCF/NumPy/SciPy modules and does not start SCF, Fock construction or optimization. Existing P12 acceptance is not recomputed or subjected to a new memory gate.

This is not native Compute. `--action Compute` refuses before discovering or starting WSL processes. Results keep `compute_enabled: false`, `image_id: null`, `native_p12_compute: NOT_IMPLEMENTED` and `scientific_acceptance: NOT_EXECUTED`. Native Check cannot substitute for Docker or P12 scientific acceptance.

## Run a Check using your actual environment

From the Windows repository directory, select your own installed distribution and Python path:

```powershell
$NativeCheckRecord = Join-Path 'D:\chem-work\native-wsl2' ('check-' + [guid]::NewGuid().ToString('N'))
python -I -B scripts/check-wsl2-runtime.py --action Check --distribution Ubuntu-24.04 --python /home/your-user/your-env/bin/python --record-dir $NativeCheckRecord
```

Replace the distribution/Python/output examples with actual paths. The record directory must be a new absolute host path. Omit `--record-dir` for JSON output only. Repeat `--source-file /path/to/an/actual/source.py` to hash selected sources; it does not execute them or scan entire source/credential directories. These arguments are passed as argv, not shell interpolation.

Check records WSL versions, distributions and their running state before calling the selected distribution normally with `--exec`. An existing stopped distribution may start through normal WSL behavior; use `--require-running` to refuse that case. The worker uses `PYTHONNOUSERSITE=1` and `-I -B`. The entry never shuts down distributions or installs/upgrades/downloads tools or changes global WSL/original scientific environments. Command timeout defaults to 30 seconds and can be >0 to at most60 seconds. Timeout, invalid JSON, missing environment/packages, root identity or mismatches fail closed.

The fingerprint includes distribution/WSL/kernel, Python executable/prefix/version, seven package metadata versions/hashes, explicit source hashes and entry/worker hashes. It is an observed identity, not an immutable environment snapshot. UID/PID1, logical/affinity CPUs, memory/swap and cgroup hierarchy counters are observations; available tools do not prove enforceable isolation. MemAvailable is not a task budget. Docker's high-cost memory profiles are neither imposed on this Check nor relaxed by it.

## Requirements for a future native Compute backend

Before opening native P12 Compute, independently implement and accept: a read-only candidate snapshot and complete actual dependency/source mapping; input/output/network isolation; owned process groups/cgroups, persistent stdout/stderr, timeouts/cancellation/TERM-to-KILL/descendant cleanup/crash recovery proven with zero-QM faults; native resource profiles and peak evidence based on delegation capability; and separately authorized low-cost/scientific acceptance. Do not install bwrap, invoke sudo or modify the original environment automatically. Two hashed scripts do not establish a full 107-file dependency contract.

The 2026-10-09 historical record has 13 simulated stdlib cases passing; a refused stopped-distribution case was retained; a later explicit Check passed with start-state false/end-state true; and Compute refused with exit2 before WSL startup. Observed WSL2.3.26.0, kernel5.15.167.4, UID1000 and Python3.12.13 belong to that machine/record, not general requirements. No scientific call or upgrade ran. Root Runtime tests are local as described in [test distribution](TEST_DISTRIBUTION.md); a public checkout does not include those private suites.
