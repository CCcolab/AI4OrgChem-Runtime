[English guide](USER_GUIDE.md) · [English README](../../README.md) · [Chinese counterpart](../../docs/SOURCE_INSTALLATION_zh-CN.md)

# Install a local Runtime from source

## What is installed, and what is needed only once?

This is the unified Runtime source/shared Docker environment installation guide, not a standalone installer per calculation module. Source still needs dependency preparation and a local image build; the dedicated source ZIP does not contain a complete installed environment and the guide ZIP is reading material. Prepare/build establishes this environment or a separate new one; it is not repeated before every calculation.

For ordinary RHF alone, follow [the complete RHF installation/use steps](CURRENT_MOLECULAR_SINGLE_POINT.md) and register only `molecular-service`. Other service registrations below are optional and do not start calculations. The original seven-task/P14 environment has a separate build/identity contract. With an existing image/service record, go directly to its run instructions and retain that record.

This installation path creates its own local image and service identities. Historical scientific acceptance never transfers automatically to a new image. It does not modify your existing research environment or global WSL configuration.

## Prerequisites and source download

Use Python 3.12+, an available Docker Linux/amd64 engine, and network access to GitHub, PyPI, Docker Hub and Debian repositories during the build. Git is required for a clone. Host scripts use the Python standard library; scientific dependencies are installed inside the image. The initial Python dependency download is approximately 161 MB, excluding the base image and system packages. The legacy Check/Report PowerShell launcher separately requires PowerShell 7.3+.

For the fixed release:

```powershell
git clone --branch v0.1.0 --depth 1 https://github.com/CCcolab/AI4OrgChem-Runtime.git D:\chem-work\runtime-v0.1.0
Set-Location D:\chem-work\runtime-v0.1.0
git rev-parse HEAD
```

To use subsequent committed maintenance changes, clone the default branch into a separate new directory instead. Record the actual commit. These English pages are a post-release documentation supplement and are not included in the immutable v0.1.0 assets.

Alternatively, download `AI4OrgChem-Runtime-source-v0.1.0.zip` from the [Release](https://github.com/CCcolab/AI4OrgChem-Runtime/releases/tag/v0.1.0), verify `SHA256SUMS.txt`, extract into a new directory, and enter the directory containing `scripts`. The named source asset contains Git commit/tree/blob proofs. GitHub's automatically generated Source code ZIP does not contain the installer's identity proofs. The guide ZIP is only a website, not an installation package.

## Prepare and build

Run in your chosen source directory. The destination must not already exist.

```powershell
python -B .\scripts\install-local-runtime.py prepare --destination D:\chem-work\runtime-install
python -B .\scripts\install-local-runtime.py build --destination D:\chem-work\runtime-install
```

`prepare` exports committed Git files or verifies the dedicated installation ZIP, downloads the pinned public scientific commit, combines three captured adapters, and checks 591 scientific files. It downloads and verifies 21 wheels and one source distribution from official PyPI. The reconstructed scientific archive has its own hash; it is not claimed to match the historical `science.tar` byte for byte.

`build` verifies the prepared context and builds from the pinned public Python base, without requiring a private historical Runtime base image. geomeTRIC is built from its fixed source distribution inside the image, with a newly recorded wheel hash. Actual Debian Git and Python versions are recorded under `/opt/install-build`. Debian repository resolution is not promised to be bit reproducible.

Keep the build logs and `built-image.json`. On failure, inspect the corresponding `*.stderr.log`; prepare a separate new directory rather than resetting an old installation or changing scientific rules.

## Register a service

Use the local tag in this installation's `built-image.json`. Each registration output directory must be new. Register only the services you need.

```powershell
Set-Location D:\chem-work\runtime-install\runtime
$installed = Get-Content ..\built-image.json -Raw | ConvertFrom-Json
python -B .\scripts\register-installation.py --service molecular-service --image $installed.local_tag --output-dir ..\installations\molecular-service
python -B .\scripts\register-installation.py --service registered-cases --image $installed.local_tag --output-dir ..\installations\registered-cases
python -B .\scripts\register-installation.py --service protocol-cases --image $installed.local_tag --output-dir ..\installations\protocol-cases
python -B .\scripts\register-installation.py --service high-cost-cases --image $installed.local_tag --output-dir ..\installations\high-cost-cases
```

Registration checks the actual image ID, base layers, platform, labels, non-root identity, dependency versions and source files. `ENGINEERING_VALIDATED` records engineering identity checks; scientific acceptance remains `UNKNOWN` until an actual qualifying run. Keep the same installation record for subsequent commands.

The `REVIEWED_PUBLIC_PAYLOAD_WITH_LOCAL_TESTS_V4` contract preserves the original source catalogs and records exact local test exclusions and permitted engineering overrides in separate installation baselines:

| Service | Original entries | Installed entries | Test exclusions | Engineering overrides | Other entries unchanged |
| --- | ---: | ---: | ---: | ---: | ---: |
| molecular-service | 20 | 20 | 0 | 3 | 17 |
| registered-cases | 37 | 37 | 0 | 3 | 34 |
| protocol-cases | 118 | 113 | 5 | 5 | 108 |
| high-cost-cases | 107 | 100 | 7 | 7 | 93 |

See [exact source bindings](../../scripts/installation_source_bindings.py). Scientific rows may not be omitted. Old acceptance remains attached to its original source, host and image.

## Output permissions and task selection

Linux output directories must be writable by both the host and UID/GID `10001:10001`. The supervisor performs an actual file-write probe before entering a scientific worker. A failed or unknown probe refuses the run. With existing `setfacl`, a dedicated new output root can retain host ownership and grant inheritable worker access:

```bash
mkdir -p "$HOME/ai4orgchem-runs"
setfacl -m u:10001:rwx -m d:u:10001:rwx "$HOME/ai4orgchem-runs"
```

Choose your own dedicated directory. Do not apply this to an existing research tree. Without ACL tools, ask your system maintainer to prepare a mutually writable output directory; the project does not install system packages or use `chmod 777`. Windows bind mounts also rely on the actual write probe.

Continue with [your molecule](CURRENT_MOLECULAR_SINGLE_POINT.md), [fixed examples](CURRENT_REGISTERED_CASES.md), [protocol cases](CURRENT_PROTOCOL_CASES.md), or [high-cost states](CURRENT_HIGH_COST_CASES.md). The [original P14 environment](CURRENT_P14_BUILD_RUN.md) is a separate build/identity contract and is not registered through these four service families.

The 2026-10-09 clean-directory installation record passed preparation/build, four registrations, 45 engineering cases and four bounded tasks. High-cost replay and a fresh-machine acceptance were not executed. Native WSL2 has recorded Check support only; native Compute is not implemented. User conditional Compute remains closed. L4 saves checkpoints but cannot resume. Public prebuilt-image distribution remains blocked.
