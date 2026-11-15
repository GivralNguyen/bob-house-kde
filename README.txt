BOB HOUSE KDE — 0.3.0

A Microsoft Bob-inspired desktop experience for KDE Plasma 6.

One-command setup from an existing KDE Plasma 6 desktop:
  ./install.sh

This installs missing supported distro packages, downloads and verifies assets,
builds the wallpaper, checks all rooms, and installs/activates it.
Run as your desktop user; only package installation uses sudo.

Options:
  ./install.sh --check          Read-only prerequisite check
  ./install.sh --prepare        Prepare and verify without changing the desktop
  ./install.sh --install-only   Prepare and register without activating
  ./install.sh --no-deps        Do not install system packages

See README.md for demo images, distro support, controls, and licensing.
Runtime artwork is downloaded separately. No images are bundled.

Create the source release:
  python3 tools/package_release.py
