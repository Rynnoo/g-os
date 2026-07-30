# G-OS

G-OS is a speedrunning-focused desktop built on Fedora Atomic KDE. The goal is a
Windows-familiar experience where a runner can install trusted tools from
**G Store**, assemble a run setup in **G Mode**, and start everything without
living in a terminal.

> [!IMPORTANT]
> This repository is an early development scaffold, not a production operating
> system. Do not install it over a computer that contains data you care about.

## What v0.1 contains

- An image definition based on Universal Blue's Fedora Atomic KDE image.
- A small, curated G Store prototype. OBS Studio, Chatterino, and Bottles use
  fixed Flathub application IDs; entries that still need packaging or legal and
  compatibility review are visible but deliberately cannot be installed.
- A G Mode prototype with validated JSON profiles, requirement checks, safe
  process launching, and a dry-run mode.
- A launchable Basic Streaming profile for OBS + Chatterino, plus an NSMBW
  profile showing how the future timer/autosplitter setup fits together.
- GitHub workflows and Bootc Image Builder configuration for container and VM
  image experiments.

G Mode does **not** move windows yet. The profile format records normalized
screen regions now so the future KWin integration can apply them consistently
across different monitor resolutions.

## Repository map

| Path | Purpose |
| --- | --- |
| `Containerfile` | Builds the G-OS bootc container image |
| `system_files/` | Files layered into the immutable operating-system image |
| `apps/g-store/` | G Store model, Flatpak backend, and optional PySide6 UI |
| `catalog/` | Curated application metadata |
| `apps/g-mode/` | G Mode profile validation, launcher, and optional UI |
| `profiles/` | Version-controlled run setup profiles |
| `disk_config/` | QCOW2 and installer ISO build settings |
| `docs/` | Architecture, app status, roadmap, and VM instructions |

## Try the application prototypes

Python 3.11 or newer is sufficient for the model and tests. PySide6 and Flatpak
are only needed to display the Linux GUI and perform real installs.

```text
python -m unittest discover -s tests -v
python apps/g-store/main.py --catalog catalog/apps.json --dry-run
python apps/g-mode/main.py --profiles-dir profiles --profile basic-streaming --dry-run
```

Use `python ... --help` for the exact options supported by each prototype. On
Windows, `py -3.11` can be used in place of `python`.

## Build and test the OS

The OS image toolchain is Linux-native. The easiest Windows-friendly route is
to publish the development container with the included GitHub Actions workflow,
run the disk-image workflow, download its installer ISO artifact, and boot it in
Hyper-V, VMware, or VirtualBox. Local builds need a Linux machine with Git,
Just, Podman, and KVM access.

Before publishing an image:

1. Set `REPO_ORGANIZATION` in `image-template.env`; the build recipes replace
   the matching ISO placeholder without modifying the tracked template.
2. Review the image name, organization, registry permissions, and floating
   base-image tag.
3. Keep the privileged Bootc Image Builder and VM-helper images on reviewed
   immutable digests; update them only with a disk/VM smoke test.
4. Run the tests, then build with `just build`.

Image signing is deliberately not wired into this starter yet. Treat its output
as an unsigned development artifact; add and verify Cosign signing before a
public release, and never commit a private signing key.

Useful Linux commands:

```text
just build
just build-qcow2
just run-vm-qcow2
just build-iso
```

See [VM testing](docs/vm-testing.md) before booting an image.

## App policy

G Store is intentionally an allowlist, not a general command runner. Catalog
records select a reviewed installer backend and a fixed identifier. They cannot
embed shell commands. Flatpak is the first supported backend because it offers
good desktop integration, predictable IDs, and app-level sandboxing. Installs
use the base image's root-protected system Flathub remote; the desktop may show
a normal graphical authorization prompt, but no terminal command is required.

Windows-only speedrunning tools will be added through reviewed Bottles/Wine
recipes only after their licenses, downloads, checksums, process-memory needs,
and hardware access have been tested. See [the app inventory](docs/app-inventory.md).

## Project status and naming

`G-OS` is a working project name. A discontinued Linux distribution previously
used the name `gOS`, so naming and trademark checks are required before a public
release.

Licensed under Apache-2.0. Third-party applications retain their own licenses
and are not automatically redistributed by this repository.
