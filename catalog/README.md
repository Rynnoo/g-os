# G Store catalog

`apps.json` is the v1 curated catalog and `schema.json` documents its JSON
shape. G Store also applies stricter validation in Python, including a fixed
app-ID-to-Flatpak-ref allowlist.

An app is actionable only when it has `status: "available"`, `enabled: true`,
and an approved install object. Planned and disabled entries must use
`enabled: false` and `install: null`, so they can be displayed without becoming
executable.

Adding an installable app requires updating both the catalog and
`apps/g-store/gstore/security.py`. This deliberate two-part review prevents a
catalog-only edit from causing an arbitrary package or command to run.

G Store manages Flatpaks through the root-protected system-scoped `flathub`
remote supplied by the G-OS base image. It does not create or trust a
user-scoped remote, and it never copies a command or URL from catalog prose.
