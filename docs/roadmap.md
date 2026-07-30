# Roadmap

## v0.1 — foundation

- Bootc image scaffold on Fedora Atomic KDE.
- Safe catalog parser and fixed-ID Flatpak backend.
- G Store and G Mode desktop launchers.
- Versioned G Mode profiles, dry-run, and requirement reporting.
- Unit tests and VM-image build configuration.

Exit condition: CI validates the source and produces a bootable test image from
a repository with its real organization configuration.

## v0.2 — first useful runner image

- Settle visual identity and public project name.
- Add browser choice and onboarding.
- Package the first custom G-OS application from a reproducible source build.
- Build a reviewed LiveSplit Bottle with a small, pinned component set.
- Add catalog signature verification and rollback.
- Add accessible install progress, cancellation, and actionable errors.

Exit condition: a new user can install OBS, chat, browser, timer, and one custom
tool without entering a terminal.

## v0.3 — real G Mode

- GUI profile editor with drag/snap screen layout.
- KWin window matching and placement on Wayland.
- OBS collection/profile/scene selection.
- Startup timeouts, retry, per-app logs, and safe session cleanup.
- Import/export profiles without including credentials.

Exit condition: one click reliably recreates a two-monitor NSMBW run setup after
a clean login.

## v0.4 — hardware and release hardening

- RetroSpy/Nintendo input-display decision and packaged integration.
- Capture-card, controller, serial, audio, and GPU compatibility matrix.
- Atomic update channels, release notes, staged rollouts, and rollback UX.
- Installer branding, recovery documentation, accessibility audit, and signed
  public releases.

Exit condition: the release candidate passes clean-install and upgrade tests on
representative AMD, Intel, and NVIDIA machines plus the supported capture/input
hardware.
