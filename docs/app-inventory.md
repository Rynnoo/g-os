# Application inventory

This is the initial G-OS application backlog. “Available” means the v0.1 store
has a fixed, reviewed Flatpak ID; it does not promise that every capture device
or plugin has been tested.

| Application | v0.1 status | Intended delivery | Work still required |
| --- | --- | --- | --- |
| OBS Studio | Available | Flathub | Test capture cards, PipeWire, plugins, and scene import |
| Chatterino | Available | Flathub | Test Twitch authentication and browser handoff |
| Bottles | Available | Flathub | Establish reviewed G-OS environments and backup policy |
| Browser | Planned | Chromium or vendor Chrome package | Choose default; review codec, sync, update, and redistribution tradeoffs |
| LiveSplit + components | Planned | Versioned Bottles recipe | Test .NET, fonts, global hotkeys, plugins, and every bundled component |
| SCU | Planned | Native package, Flatpak, or Bottle | Supply source/repository, license, build steps, runtime, and hardware permissions |
| AutoSplit64 | Planned | Native package, Flatpak, or Bottle | Supply source/repository, license, build steps, runtime, and process access needs |
| NSMBW autosplitter | Planned | Bundled with its tested timer/emulator stack | Identify supported Dolphin build, memory-reading method, and release artifacts |
| Gcord | Planned | Native package or Flatpak | Supply source/repository, license, build steps, runtime, and authentication needs |
| RetroSpy | Planned | Reviewed upstream binary or source build | Test Linux release, serial/USB permissions, controllers, and layouts |
| NintendoSpy | Planned/legacy | Prefer RetroSpy unless compatibility requires it | Confirm exact fork, license, supported hardware, and Wine behavior |

## Intake checklist for a custom app

Before a custom program gets an install button, record:

- canonical source repository and project owner;
- redistribution license and licenses of bundled components;
- supported CPU architectures and Linux/Windows runtime requirements;
- reproducible build and test commands;
- immutable release URL, version, size, and SHA-256 checksum;
- required files, network hosts, devices, portals, and process access;
- update and rollback strategy;
- a clean-VM install, launch, update, and uninstall test;
- any other app that must share its Wine prefix or permissions.

## Proposed LiveSplit bundle policy

Do not label a component “preconfigured” until its exact version is pinned and
tested. The bundle should publish a compatibility matrix containing the
LiveSplit version, Wine/Bottles runner, .NET runtime, component versions,
supported games/emulators, and known limitations. User layouts and split files
must live outside the read-only application bundle so updates cannot overwrite
them.

