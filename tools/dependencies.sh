#!/usr/bin/env bash
# Sourced by install.sh. Package commands retain their normal confirmation prompt.
find_qdbus() {
    local candidate
    for candidate in qdbus6 qdbus-qt6 /usr/lib/qt6/bin/qdbus /usr/lib64/qt6/bin/qdbus; do
        if command -v "$candidate" >/dev/null 2>&1; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

check_platform() {
    local version
    if ! command -v plasmashell >/dev/null 2>&1; then
        echo 'KDE Plasma 6 must already be installed. This installer does not install a desktop environment.' >&2
        return 1
    fi
    # Some Plasma builds wait on session services even for --version.
    command -v timeout >/dev/null || { echo 'GNU coreutils (timeout) is required.' >&2; return 1; }
    version=$(timeout 10 env QT_QPA_PLATFORM=offscreen LC_ALL=C plasmashell --version 2>/dev/null || true)
    if [[ ! "$version" =~ plasmashell[[:space:]]6\. ]]; then
        echo "KDE Plasma 6 is required; found: $version" >&2
        return 1
    fi
    if ! command -v systemctl >/dev/null 2>&1; then
        echo 'This installer requires a systemd user session for Plasma layout changes.' >&2
        return 1
    fi
}

missing_dependencies() {
    MISSING=()
    [[ -x /usr/bin/python3 ]] || MISSING+=(python)
    if [[ ! -x /usr/bin/python3 ]] || ! timeout 20 /usr/bin/python3 "$PROJECT_DIR/tools/check_qt.py" >/dev/null 2>&1; then
        MISSING+=(qt)
    fi
    find_qdbus >/dev/null || MISSING+=(qdbus)
    command -v desktop-file-validate >/dev/null || MISSING+=(desktop)
    if ! command -v xdg-mime >/dev/null || ! command -v xdg-open >/dev/null; then MISSING+=(xdg); fi
}

select_package_manager() {
    local distro=$1 like=$2
    PACKAGE_MANAGER=''
    case "$distro $like" in
        *arch*|cachyos*|endeavouros*|manjaro*) PACKAGE_MANAGER=pacman ;;
        fedora\ *) PACKAGE_MANAGER=dnf ;;
        debian\ *|ubuntu\ *) PACKAGE_MANAGER=apt-get ;;
    esac
}

packages_for_missing() {
    PACKAGES=()
    local need
    for need in "${MISSING[@]}"; do
        case "$PACKAGE_MANAGER:$need" in
            pacman:python) PACKAGES+=(python) ;;
            pacman:qt) PACKAGES+=(pyside6 qt6-declarative qt6-svg) ;;
            pacman:qdbus) PACKAGES+=(qt6-tools) ;;
            dnf:python) PACKAGES+=(python3) ;;
            dnf:qt) PACKAGES+=(python3-pyside6 qt6-qtdeclarative qt6-qtsvg) ;;
            dnf:qdbus) PACKAGES+=(qt6-qttools) ;;
            apt-get:python) PACKAGES+=(python3) ;;
            apt-get:qt) PACKAGES+=(python3-pyside6.qtquick python3-pyside6.qtwidgets
                python3-pyside6.qtsvg python3-pyside6.qtnetwork python3-pyside6.qttest
                qml6-module-qtquick-controls qml6-module-qtquick-layouts qml6-module-qtqml-workerscript) ;;
            apt-get:qdbus) PACKAGES+=(qdbus-qt6) ;;
            *:desktop) PACKAGES+=(desktop-file-utils) ;;
            *:xdg) PACKAGES+=(xdg-utils) ;;
        esac
    done
}

install_missing_dependencies() {
    local ID='' ID_LIKE=''
    if [[ -r /etc/os-release ]]; then source /etc/os-release; fi
    select_package_manager "$ID" "$ID_LIKE"
    if [[ -z "$PACKAGE_MANAGER" || -e /run/ostree-booted ]]; then
        echo "Automatic package installation is unavailable on this distribution. Missing: ${MISSING[*]}" >&2
        echo 'Install the requirements listed in README.md, then rerun ./install.sh --no-deps.' >&2
        return 1
    fi
    command -v "$PACKAGE_MANAGER" >/dev/null || { echo "Missing package manager: $PACKAGE_MANAGER" >&2; return 1; }
    command -v sudo >/dev/null || { echo 'Install the requirements as an administrator; sudo is unavailable.' >&2; return 1; }
    packages_for_missing
    echo "Installing required packages using $PACKAGE_MANAGER: ${PACKAGES[*]}"
    case "$PACKAGE_MANAGER" in
        pacman) sudo pacman -S --needed "${PACKAGES[@]}" ;;
        dnf) sudo dnf install "${PACKAGES[@]}" ;;
        apt-get) sudo apt-get install "${PACKAGES[@]}" ;;
    esac
}
