# G Mode v0.1

G Mode loads strict JSON session profiles, checks whether their G Store apps
are installed, and starts registered native or Flatpak applications in the
saved order. Profiles contain catalog IDs rather than executable commands, so
profile files are not a shell-command execution surface.

The v0.1 launcher registry contains the G Store's fixed Flatpak targets for
OBS Studio, Chatterino, and Bottles, plus fixed native Chrome paths.
Flatpak requirements are satisfied only by the root-protected system
installation managed by G Store; user-installed lookalike applications do not
satisfy the check.

Built-in launchers use fixed `/usr/bin` executable paths, so changing a user's
`PATH` cannot substitute another program during a requirement check or launch.
Planned catalog entries such as LiveSplit Complete and the NSMBW Autosplitter
remain deliberately unlaunchable until their package targets are finalized.

The profile model, validation, requirement checks, and dry run use only the
Python 3.11 standard library. PySide6 is optional and imported only when the
graphical interface starts.

```text
python apps/g-mode/main.py --help
python apps/g-mode/main.py --list
python apps/g-mode/main.py --profile basic-streaming --check
python apps/g-mode/main.py --profile basic-streaming --dry-run
python apps/g-mode/main.py
```

`basic-streaming` is the launchable integration example for the currently
available OBS Studio and Chatterino packages. `nsmbw-starter` records the target
NSMBW layout, but a real launch remains blocked until its LiveSplit and
autosplitter packages are reviewed and registered.

`G_OS_PROFILES_DIR` can override the profile directory. Installed systems use
`/usr/share/g-os/profiles`; source checkouts fall back to the repository's
`profiles` directory.

## Current boundary

Version 0.1 saves monitor-relative window placements, startup timeout, and
session toggles, but does not yet apply window positions, wait for windows, or
change system session settings. Both the schema and UI state this limitation.
