# GDID F!K — Windows Global Device ID Toolkit

A small, self-contained Windows GUI tool to **inspect, back up, and (in a controlled test
environment) manipulate or disable** the Windows "Global Device ID" (GDID) — the persistent
device identifier Microsoft uses to track a Windows installation across MSA-linked services.

Available in **English** and **German**, switchable at runtime.

> Public background: Microsoft confirmed the existence of GDID after it surfaced in an FBI
> complaint that used it to correlate a suspect's Windows installation across VPN hops
> ([gHacks](https://www.ghacks.net/2026/07/12/microsoft-confirms-windows-gdid-device-identifier-that-cannot-be-disabled-documented-in-fbi-case-filing/),
> [Windows Latest](https://www.windowslatest.com/2026/07/10/you-cant-fully-disable-microsofts-gdid-windows-11-tracker-but-these-settings-limit-what-it-captures/)).

## What it does

- Reads the GDID/LID from the known registry locations:
  - `HKCU\SOFTWARE\Microsoft\IdentityCRL\ExtendedProperties` → `LID`
  - `HKLM\SOFTWARE\Microsoft\IdentityStore` → `DeviceId`, `LID`
  - `HKLM\SOFTWARE\Microsoft\IdentityCRL\NegativeCache` → related token scopes
- Derives the human-readable GDID (`g<decimal>`) from the raw hex LID
- Shows the status and start type of the `wlidsvc` service (Microsoft Account Sign-in Assistant),
  which provisions and reports the identifier
- Lets you, on your own test machine / VM:
  - Create a timestamped JSON backup of all current values before any change
  - Replace the LID with a random value
  - Delete the LID
  - Restore any previous backup
  - Disable + stop `wlidsvc` (prevents new GDIDs from being generated/reported)
  - Re-enable `wlidsvc`
  - Jump straight to the relevant key in `regedit`
  - Export the action log

## ⚠️ Disclaimer

This tool changes system identity/registry state and can affect Microsoft Account sign-in,
Windows activation, and Microsoft Store functionality. **Only use it on systems you own or
are explicitly authorized to test (e.g. a disposable VM).** Every mutating action creates an
automatic backup first, but there is no guarantee changes are fully reversible on every
Windows build. Use at your own risk.

This project is not affiliated with or endorsed by Microsoft. "GDID" and related identifiers
are Microsoft's terminology, documented here for transparency and testing purposes only.

## Download

Grab the latest standalone `.exe` from the [Releases](../../releases) page — no Python
installation required.

## Running from source

Requires Python 3.10+ (uses only the standard library — `tkinter`, `winreg`).

```powershell
python gdid_gui.py
```

To use the admin-only features (HKLM values, service control), start it elevated, or use the
in-app "Restart as administrator" button.

## Building the EXE yourself

```powershell
pip install pyinstaller
pyinstaller --noconfirm --onefile --windowed --name "GDID F!K" gdid_gui.py
```

The output lands in `dist\GDID F!K.exe`. A GitHub Actions workflow
(`.github/workflows/build.yml`) does this automatically on every tagged release.

## Project layout

```
gdid_gui.py          Main application (GUI, registry + service logic, EN/DE translations)
GDID-Reader.ps1       Standalone read-only PowerShell script (no GUI, quick CLI check)
```

## License

MIT — see [LICENSE](LICENSE).
