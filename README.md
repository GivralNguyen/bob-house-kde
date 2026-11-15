# Bob House KDE

Unofficial · Version 0.3.0 · Runtime assets downloaded separately

A Microsoft Bob-inspired desktop experience for KDE Plasma 6, with ten
interactive rooms, animated Rover, and clickable objects that open your apps,
folders, and websites.
Runtime artwork and generated runtime files are not included. The setup command downloads assets separately from third-party hosts before building and installing.

## What it looks like

The original Microsoft Bob, for reference

[![The Study in the original Microsoft Bob, with Rover (image hosted on Reddit)](https://i.redd.it/70p0jdlwept81.png)](https://i.redd.it/70p0jdlwept81.png)


## Features

- Study, Family Room, Kitchen, Attic, Garage, Sun Room, Kid's Room, Safe,
  Mouse Hole, and Outside, with per-screen room selection.
- Animated Rover with vector artwork and expressive animation sequences.
- Working clock hands, grandfather-clock pendulum, and calendar date.
- Individual shortcuts for each object, even when objects share a type.
- Native notes, calendar notes, timer, application picker, and room chooser.
- Financial Guide and Checkbook objects, opening a calculator.

This is a wallpaper plugin plus native tools, not a complete KDE global theme
or an emulator of Microsoft Bob's applications. Four existing door destinations
are mapped to connect all ten room types. Rover's hints and commands are local.

## Install

Start from an existing **KDE Plasma 6** desktop with a systemd user session.
Extract the release into a permanent folder and run:

```bash
./install.sh
```

The installer checks prerequisites, installs missing supported distro packages,
downloads and checksum-verifies the assets, builds the rooms and animations,
verifies all ten rooms and object shortcuts, then installs and activates the
wallpaper. It stops on any failed step before activation.

Only dependency installation uses `sudo`; run the script as your regular user.
The package manager displays its transaction and asks for confirmation. No
package installation runs when the prerequisites are already available.
The script does not install KDE, switch desktop environments, add repositories,
perform a system upgrade, or install Python packages through `sudo pip`.

### Dependency support

| Distribution | Automatic dependency installation |
| --- | --- |
| Arch, CachyOS, EndeavourOS, Manjaro | `pacman -S --needed` |
| Fedora, conventional installation | `dnf install` |
| Debian / Ubuntu with Plasma 6 and packaged PySide6 | `apt-get install` |
| Other distributions or immutable Fedora | Install prerequisites manually, then use `./install.sh --no-deps` |

Package availability depends on the distribution release and enabled repositories.
Debian 13 and recent Ubuntu releases package PySide6; older releases may not.
If the package manager reports unavailable packages, update your package indexes
or install suitable packages manually; the script does not add third-party repos.
Arch users should keep their system fully updated before installing packages.
Cross-distribution package transactions have not been tested on live systems.

Required: system Python 3.10+, PySide6 (QtQuick, QtWidgets, QtSvg, QtNetwork,
QtTest), QtQuick Controls/Layouts QML modules, Qt 6 qdbus, `desktop-file-validate`,
`xdg-mime`, and `xdg-open`. The script checks `/usr/bin/python3`, the interpreter
used by the installed helper. QtWebEngine is not needed.
Qt 6 qdbus executable names and locations are detected per distribution.

Package references: [Arch PySide6](https://archlinux.org/packages/extra/x86_64/pyside6/),
[Fedora PySide6](https://packages.fedoraproject.org/pkgs/python-pyside6/python3-pyside6/),
[Debian PySide6](https://packages.debian.org/trixie/python3-pyside6.qtquick),
[Ubuntu PySide6](https://packages.ubuntu.com/search?keywords=python3-pyside6.qtquick).

### Installer options

| Command | Behavior |
| --- | --- |
| `./install.sh` | Complete setup and wallpaper activation |
| `./install.sh --check` | Read-only dependency/platform check; no downloads or changes |
| `./install.sh --prepare` | Dependencies, download, build, and verification; no desktop changes |
| `./install.sh --install-only` | Complete preparation and register plugin/helper, without activating |
| `./install.sh --no-deps` | Complete setup but fail on missing dependencies instead of installing packages |

`--no-deps` can also be combined with `--prepare` or `--install-only`.
Preparation needs Plasma 6 installed but does not need a running desktop session.
Activation and registration must run inside your Plasma desktop session.

### Asset downloads

The downloader fetches Rover's `ROVER.ACT` from TMAFE and the room data/WMFs
from wuffs.org. TMAFE currently redirects the actor download to tmafemirror.org;
that mirror is explicitly allowed and the same pinned checksum is required. Exact URLs, expected sizes, and SHA-256 checksums are recorded
in [asset-downloads.json](asset-downloads.json). To inspect them without downloading:

```bash
python3 tools/download_assets.py --list
```

Downloads are staged and checked before the `assets/` directory is created.
A network failure, unexpected response, or checksum mismatch leaves no partial
asset installation. A repeat run verifies existing assets and skips downloads;
it refuses to overwrite a changed or incomplete asset directory. Move that
directory aside to fetch a fresh set. Upstream changes require reviewing and
updating the manifest; checksums verify that the downloaded files match the expected bytes.

Do not use sudo. The script installs for your user and activates the wallpaper
on all connected desktops. It backs up the previous wallpaper and layout, then
switches to KDE's Desktop layout so room objects receive clicks. Your desktop
files remain in the Desktop folder; panels and application windows remain.
Plasma may restart while changing layouts. Keep the extracted folder in place:
the wallpaper's artwork and native action helper refer to that location.

Check dependencies without making changes:

```bash
./install.sh --check
```

Install files without activating (also used for updates):

```bash
./install.sh --install-only
```

The install-only option registers the plugin and helper but does not configure
an artwork path on a desktop. To select it manually, choose Bob House KDE
in Wallpaper settings and set Local Bob artwork directory to this folder's
assets directory as a file:// URL. Normal ./install.sh does this automatically.
After updating an already active package, log out and back in to refresh QML.

Restore the previous wallpaper and desktop layout:

```bash
./restore-wallpaper.sh
```

Building and verifying the project does not change your wallpaper.
Activation happens only in the final installation step.

## Controls

| Action | Result |
| --- | --- |
| Click object | Open its application, folder, or tool |
| Shift-click object | Assign an app, folder, or website |
| F1 / Objects | Show clickable object names |
| F2 / click Rover | Open Rover's command menu |
| Rooms | Choose any room |
| Options | Change animation/name-display settings |
| Right-click desktop | KDE's usual desktop menu |

Books open Documents, albums open Pictures, cabinets open Home. Financial Guide
and Checkbook launch an installed calculator; the Microsoft Bob finance software
is not reimplemented. Default email needs a configured mail application.
Missing or unwanted destinations can be changed with Shift-click.
Notes use the Save button. Timer notifications require sound enabled in options.
Internet is required for the initial asset download and any online destinations. The built wallpaper works offline.

Settings: ~/.config/bob-house-kde/settings.json
Wallpaper/layout backup: ~/.local/state/bob-house-kde/
Installed plugin: ~/.local/share/plasma/wallpapers/org.bobhouse.desktop/
XDG_CONFIG_HOME, XDG_STATE_HOME, and XDG_DATA_HOME are respected.
Room and animation preferences are saved by Plasma per desktop.

## Build and verify

After downloading assets, generate runtime files:

```bash
python3 build.py
```

Check room layouts, all object protocol requests, and QML room loading:

```bash
python3 tools/verify_local.py
```

Build a source-only release ZIP and SHA-256 checksum (no assets required):

```bash
python3 tools/package_release.py
```

Output: `dist/bob-house-kde-0.3.0-source.zip`
An explicit source-file allowlist excludes runtime assets, generated `Data.js`,
generated previews, personal settings, caches, Git history, and previous builds—even after
you download and build locally. `.gitignore` also excludes downloaded asset inputs and
outputs. No images are bundled; the README's screenshot is linked from Reddit.
Do not force-add ignored runtime files when publishing.

Run downloader and installer tests without downloads or package/desktop changes:

```bash
python3 -m unittest discover -s tests -v
```

## License and provenance

I claim no ownership or rights to any assets used by this project. All assets belong to their respective owners.

The project implementation code is [MIT licensed](LICENSE). Runtime assets are
downloaded separately from TMAFE and wuffs.org during setup, then processed locally.
See [THIRD_PARTY_NOTICES.txt](THIRD_PARTY_NOTICES.txt) for attribution and
[asset-downloads.json](asset-downloads.json) for source URLs and checksums.

The download/build flow and all ten rooms are checked locally with Qt's
offscreen renderer. Cross-distribution installation testing remains outstanding.
