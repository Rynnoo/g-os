# Contributing to G-OS

G-OS is at the prototype stage. Small, reviewable changes with tests are the
most useful contributions.

## Development checks

Run from the repository root:

```text
python -m unittest discover -s tests -v
```

If `just` is installed on Linux, also run:

```text
just check
just lint
```

## Adding a catalog entry

An entry is `planned` until its source, license, permissions, update behavior,
and clean-VM lifecycle have been reviewed. Installation data must select an
existing backend and provide its fixed identifier; it must never contain shell
syntax or an arbitrary command.

Include tests for valid parsing and each relevant rejection case. For a
downloaded artifact, document the immutable release URL and checksum in the
review even if the backend implementation is not ready yet.

## Adding a G Mode profile

Use only documented schema fields and stable application IDs. Do not include
passwords, OAuth tokens, stream keys, cookies, absolute home-directory paths,
or other machine-specific secrets. Test the profile with dry-run before a real
launch.

## Image changes

Keep runtime application data outside the immutable image. Explain why a new
RPM belongs in the base image instead of Flatpak or a container, and verify that
the image still builds from scratch. Never replace signing placeholders with a
private key.
