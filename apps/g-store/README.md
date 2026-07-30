# G Store v0.1

G Store is the curated, graphical software center for G-OS. Its first version
shows the full speedrunning roadmap and provides one-click system Flatpak
installation/removal for OBS Studio, Chatterino, and Bottles.

The catalog and installer are pure Python 3.11 and do not import the optional
GUI dependency. The desktop interface requires PySide6.

From a source checkout:

```text
python apps/g-store/main.py
python apps/g-store/main.py --validate-catalog
python apps/g-store/main.py --dry-run
python -m unittest discover -s tests -p "test_gstore.py" -v
```

The installed launcher can run:

```text
/usr/bin/python3 /usr/libexec/g-os/apps/g-store/main.py
```

When a source-tree catalog is unavailable, the app reads
`/usr/share/g-os/catalog/apps.json`.

## Security model

Catalog records contain data, never commands. Unknown JSON fields are rejected.
An enabled target must match an app-ID-to-Flatpak-ref mapping compiled into
`gstore/security.py`, use the `flatpak` backend, and use the `flathub` remote.
Commands are fixed argument vectors, run without a shell or `sudo`. G Store
uses only the root-protected system-scoped `flathub` remote configured by the
G-OS base image; it never creates or trusts a user-controlled remote. Flatpak
may show a graphical Polkit authorization prompt for an install or removal.
Adding another installable app intentionally requires both catalog and code
review.

Removal leaves user application data in place. Planned and disabled entries are
visible but have no install metadata and cannot reach the command runner.
