# G-OS architecture

## Product layers

G-OS has three intentionally separate layers:

1. **The image** supplies Fedora Atomic KDE, drivers, desktop defaults, Python,
   PySide6, and the two G-OS launchers. Atomic updates make rollback possible
   when an OS update causes a regression.
2. **G Store** reads a versioned, validated catalog and maps reviewed entries to
   narrowly defined installation backends. The first backend is Flatpak.
3. **G Mode** reads a versioned run profile, checks requirements, launches its
   applications in order, and will eventually ask KWin to place their windows.

Keeping these layers separate lets the store and launcher be tested on an
ordinary Fedora desktop before anyone builds or installs a full OS image.

## Trust boundaries

Catalog and profile files are untrusted input even when they are stored in this
repository. Parsers must reject unknown schema versions, missing required
fields, invalid IDs, path traversal, malformed screen regions, duplicate IDs,
and values of the wrong type.

An installer backend owns command construction. Catalog data may provide an
allowlisted package identifier, but never a command line. Subprocesses use
argument arrays with `shell=False`; app IDs are validated before execution.

Planned production requirements include:

- signing release images with Cosign;
- signing catalog releases independently so catalog updates do not require an
  OS rebuild;
- pinning downloadable artifacts by version and cryptographic checksum;
- showing source, license, permissions, and compatibility notes before install;
- keeping system-wide changes behind an authenticated, narrowly scoped helper;
- retaining the previous catalog and OS deployment for rollback.

Catalog signature verification and custom G-OS privileged helpers are not
implemented in v0.1. Until they are, the catalog ships inside the image and
should only change through reviewed image updates.

Bootc Image Builder still requires a privileged container for local disk-image
creation. Its image and the less-privileged QEMU web-console helper are pinned
to reviewed digests. The normal QEMU recipe receives only `/dev/kvm`,
`/dev/net/tun`, and `NET_ADMIN`; it is not granted full container privilege.

## G Store flow

```text
catalog/apps.json
        |
        v
schema validation --> searchable app model --> backend allowlist
                                                |
                                                v
                         root-protected system Flathub remote
                                                |
                                                v
                                  flatpak install/uninstall <fixed app ID>
```

An entry can be `available` or `planned`. Planned entries remain visible so the
product direction is honest, but the UI must not synthesize an install action
for them. All current installs and removals use system scope. The remote is
created by the trusted base image rather than catalog data or a user-controlled
remote name; Flatpak's system helper may request authorization through Polkit.

Longer term, G Store can move to a branded/configured Bazaar frontend if that
provides the required safety and presentation without maintaining a full app
store ourselves. The catalog and compatibility work remain useful either way.

## G Mode flow

```text
profile JSON --> schema validation --> requirement checks --> launch plan
                                                           |
                                      dry run <-------------+----> subprocesses
                                                                    |
                                                                    v
                                                          future KWin placement
```

Profiles store positions as fractions of a chosen screen rather than raw
pixels. For example, `[0.0, 0.0, 0.5, 1.0]` represents the left half of the
screen. A future KWin bridge will match windows using stable properties such as
desktop file ID, Wayland app ID, or window class, then translate the region to
the selected monitor's usable geometry.

The Basic Streaming profile is the executable integration example because all
of its required apps are currently installable. The NSMBW profile is a forward
compatible design sample and remains blocked during a real launch until its
LiveSplit and autosplitter targets are packaged and registered.

The future session controller must report launch failures per application. A
partial launch should stay visible to the user and offer cleanup; it must not
silently terminate unrelated processes.

## Windows compatibility

Classic LiveSplit and several community autosplitters are Windows applications.
They should be treated as a compatibility subsystem, not ordinary native apps.
One reviewed Bottle per compatibility family gives G-OS control over Wine
version, .NET dependencies, permissions, files, and rollback.

Process-reading autosplitters are the hardest case. If the game/emulator and
autosplitter run in different Wine prefixes—or one is native Linux—the expected
Windows process may not exist in a form the autosplitter can inspect. Each
game-specific stack therefore needs an end-to-end compatibility test rather
than assuming that “it starts under Wine” means it works.
