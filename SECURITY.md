# Security policy

G-OS is pre-release software. Test it only on disposable virtual machines or
spare hardware and keep independent backups of layouts, splits, recordings,
and credentials.

## Reporting a vulnerability

Until a private reporting address is established, do not post secrets, working
exploits, signing keys, tokens, or personally identifying logs in a public
issue. Contact the repository owner privately and include the affected commit,
impact, reproduction steps, and the least sensitive diagnostic material that
demonstrates the problem.

## High-risk areas

Reports are especially useful for:

- catalog validation or any path from catalog data to arbitrary command
  execution;
- signature/checksum bypasses and update rollback failures;
- Flatpak permission escalation or unsafe host filesystem access;
- Wine prefix escapes and untrusted Windows installers;
- G Mode launching a different executable than the profile displays;
- credential leakage through profiles, logs, exports, or bug reports;
- unsafe device permissions for capture cards, controllers, or serial input.

## Maintainer rules

- Never commit Cosign private keys, OAuth tokens, browser profiles, stream keys,
  or test-user credentials.
- Do not add raw shell commands to catalog or profile schemas.
- Pin third-party downloads to an immutable version and checksum.
- Never replace the digest-pinned privileged image-builder or VM helper with a
  floating container tag; review and smoke-test deliberate digest updates.
- Review requested permissions and licenses before enabling an install action.
- Treat every Wine installer and speedrunning plugin as executable code.
- Test update, uninstall, rollback, offline, and corrupted-input paths.
