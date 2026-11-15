#!/usr/bin/env bash
set -euo pipefail
PROJECT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
source "$PROJECT_DIR/tools/dependencies.sh"
MODE=activate
MODE_SET=false
INSTALL_DEPS=true
for argument in "$@"; do
    case "$argument" in
        --check|--prepare|--install-only)
            if $MODE_SET; then echo 'Choose only one of --check, --prepare, or --install-only.' >&2; exit 2; fi
            MODE=${argument#--}; MODE_SET=true ;;
        --no-deps) INSTALL_DEPS=false ;;
        --help|-h)
            echo 'Usage: ./install.sh [--check|--prepare|--install-only] [--no-deps]'
            echo 'Default: install missing dependencies, download assets, build, verify, and activate.'
            echo '--check: read-only prerequisite check; --prepare: build and verify without desktop changes.'
            exit 0 ;;
        *) echo "Unknown option: $argument. Use --help." >&2; exit 2 ;;
    esac
done
if (( EUID == 0 )) && [[ "$MODE" != check ]]; then
    echo 'Run as your desktop user, without sudo. Only package installation uses sudo.' >&2; exit 1
fi
check_platform
missing_dependencies
if [[ "$MODE" == check ]]; then
    if (( ${#MISSING[@]} )); then echo "Missing prerequisites: ${MISSING[*]}" >&2; exit 1; fi
    echo 'Prerequisites available. Installation will fetch/check assets, build, and verify automatically.'
    exit 0
fi
if (( ${#MISSING[@]} )); then
    if ! $INSTALL_DEPS; then echo "Missing prerequisites: ${MISSING[*]}. See README.md." >&2; exit 1; fi
    install_missing_dependencies
    missing_dependencies
    if (( ${#MISSING[@]} )); then
        echo "Requirements still missing: ${MISSING[*]}. Check distro package availability and Python version." >&2
        /usr/bin/python3 "$PROJECT_DIR/tools/check_qt.py" || true
        exit 1
    fi
fi
cd "$PROJECT_DIR"
if [[ "$MODE" != prepare ]]; then
    # Read-only session check before fetching or changing wallpaper state.
    /usr/bin/python3 - <<'PY'
import install_kde
if not install_kde.snapshot():
    raise SystemExit('No Plasma desktop found. Run inside a Plasma 6 session, or use --prepare.')
PY
fi
echo 'Checking and downloading assets…'
/usr/bin/python3 tools/download_assets.py
echo 'Building room artwork and Rover animations…'
/usr/bin/python3 build.py
echo 'Verifying all rooms and object shortcuts…'
QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software /usr/bin/python3 tools/verify_local.py
if [[ "$MODE" == prepare ]]; then
    echo 'Prepared and verified. Desktop unchanged. Run ./install.sh to activate.'
    exit 0
fi
if [[ "$MODE" == install-only ]]; then
    exec /usr/bin/python3 install_kde.py install
fi
exec /usr/bin/python3 install_kde.py activate
