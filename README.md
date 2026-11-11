# Telegram Desktop — local admin prototype

This repository branch contains a **local-only companion admin service prototype** for experimenting with test balances and local test identifiers.

## Important boundaries

- It does not replace Telegram's production servers or MTProto.
- It does not mint, transfer, or redeem real Telegram Stars.
- It does not access Fragment, reserve collectible usernames, or provision real +888 numbers.
- The phone-like value is deliberately a non-routable `TEST-888-XXXXXXXX` identifier.
- Do not use this prototype to collect Telegram login codes, passwords, session files, or authentication tokens.

## Run locally

Python 3.10+ is enough; no third-party packages are required.

PowerShell:

```powershell
$env:LOCAL_ADMIN_TOKEN = "change-this-to-a-long-random-secret"
python .\local-admin\server.py
```

Open http://127.0.0.1:8765 and paste the same token into the page.

Linux/macOS:

```bash
export LOCAL_ADMIN_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python3 local-admin/server.py
```

The service binds only to `127.0.0.1`. The SQLite database is created at `local-admin/data/admin.sqlite3`.

## Current status

This is the companion prototype, **not yet embedded as a native tab in Telegram Desktop**. The Telegram Desktop 7.4.1 source tree must be imported and patched separately before producing a modified Telegram executable. The GitHub Actions workflow in this branch validates the prototype; it does not claim to compile Telegram Desktop.

## License

Telegram Desktop is licensed under GPLv3 with an OpenSSL exception. Preserve upstream notices and comply with the licenses of Telegram Desktop and all bundled dependencies when importing or redistributing its source.
