# Testing G-OS in a virtual machine

Yes—test images in a VM first. An installer ISO is the most portable artifact
for a Windows development computer.

## Recommended path from Windows

1. Push the repository to GitHub after setting `REPO_ORGANIZATION` in
   `image-template.env`.
2. Let the container-image workflow publish `ghcr.io/<owner>/g-os:latest`, then
   make that development package public in GitHub Container Registry. The
   current installer does not provision credentials for a private package.
3. Run the manual disk-image workflow. It produces separate QCOW2 and
   `anaconda-iso` artifacts from that published image.
4. Download and extract the ISO artifact.
5. Create a Generation 2 Hyper-V VM, or a Fedora 64-bit VM in VMware/VirtualBox.
6. Assign 4 virtual CPUs, 8 GB RAM, a 64 GB virtual disk, UEFI firmware, and the
   installer ISO. These are comfortable development defaults, not minimums.
7. Disable Secure Boot for the earliest unsigned experiments. Re-enable and
   explicitly test it once the release signing/boot chain is configured.
8. Install only to that empty virtual disk, reboot without the ISO, and take a
   clean snapshot before testing application installs.

The starter workflow does not sign images. Its artifacts are for disposable
development VMs only, not distribution to end users.

The Linux-native local route is:

```text
just build
just build-qcow2
just run-vm-qcow2
```

`just build-qcow2` imports the rootless image made by `just build` into rootful
Podman storage for Bootc Image Builder. Use `just rebuild-qcow2` instead when a
fresh rootful build is preferable. The run command uses KVM through a container
and exposes a console at `http://localhost:8006`. It grants only the KVM/TUN
devices and `NET_ADMIN` capability recommended by that helper rather than full
container privilege. It requires working hardware virtualization, `/dev/kvm`,
and `/dev/net/tun`, so it is best run on a Linux host. Building inside a Windows
VM may require nested virtualization and is more fragile than using CI to
create the ISO.

## VM test checklist

- The environment boots and G Store/G Mode appear in KDE's application menu.
- Installation targets only the disposable VM disk.
- The installed system reboots; after a test update, the prior deployment is
  available for rollback.
- G Store opens without a terminal, searches correctly, and clearly disables
  planned entries.
- Installing and removing each available test app invokes only its reviewed
  backend and fixed application ID.
- G Mode validates the starter profile, shows missing requirements, and its
  dry-run matches the expected launch order.
- After OBS and Chatterino are installed, the Basic Streaming profile launches
  both through the reviewed registry (window placement remains a v0.1 preview).
- A failed application launch does not crash the entire session.
- Screen scaling at 100%, 125%, 150%, and 200% leaves both apps usable.
- Offline startup produces useful errors and does not damage catalog state.

## What a VM cannot prove

VM graphics, latency, capture performance, global hotkeys, USB/serial input
devices, capture cards, and anti-cheat/process-memory behavior can differ
substantially from real hardware. Use USB passthrough only with test devices,
then repeat the final compatibility matrix on a spare physical PC before
calling a release stable.
