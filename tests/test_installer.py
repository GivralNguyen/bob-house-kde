"""Exercise the install flow with fake package/system commands; no host changes."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import install_kde

ROOT = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'tools').mkdir()
        self.log = self.root / 'events'
        self.env = dict(os.environ, TEST_LOG=str(self.log))
        fake = self.root / 'python'
        fake.write_text('''#!/bin/bash
printf '%s\\n' "$*" >> "$TEST_LOG"
[[ "$1" == - ]] && cat >/dev/null
if [[ "$1" == "${FAIL_STAGE:-never}" ]]; then exit 1; fi
exit 0
''')
        fake.chmod(0o755)
        script = (ROOT / 'install.sh').read_text().replace('/usr/bin/python3', str(fake))
        (self.root / 'install.sh').write_text(script)
        (self.root / 'tools/dependencies.sh').write_text('''
check_platform() { return 0; }
missing_dependencies() { MISSING=(); if [[ "${FAKE_MISSING:-0}" == 1 ]]; then MISSING=(qt); fi; }
install_missing_dependencies() { echo packages >> "$TEST_LOG"; FAKE_MISSING=0; }
''')

    def run_installer(self, *args, **extra):
        env = dict(self.env, **extra)
        return subprocess.run(['bash', 'install.sh', *args], cwd=self.root, env=env,
                              capture_output=True, text=True)

    def events(self):
        return self.log.read_text().splitlines() if self.log.exists() else []

    def test_check_makes_no_changes(self):
        self.assertEqual(self.run_installer('--check').returncode, 0)
        self.assertEqual(self.events(), [])

    def test_prepare_order_and_no_activation(self):
        self.assertEqual(self.run_installer('--prepare').returncode, 0)
        self.assertEqual(self.events(), ['tools/download_assets.py', 'build.py', 'tools/verify_local.py'])

    def test_default_installs_missing_deps_and_activates_last(self):
        self.assertEqual(self.run_installer(FAKE_MISSING='1').returncode, 0)
        self.assertEqual(self.events(), ['packages', '-', 'tools/download_assets.py', 'build.py',
                                         'tools/verify_local.py', 'install_kde.py activate'])

    def test_verify_failure_prevents_installation(self):
        self.assertNotEqual(self.run_installer(FAIL_STAGE='tools/verify_local.py').returncode, 0)
        self.assertNotIn('install_kde.py activate', self.events())

    def test_download_failure_prevents_build(self):
        self.assertNotEqual(self.run_installer(FAIL_STAGE='tools/download_assets.py').returncode, 0)
        self.assertNotIn('build.py', self.events())

    def test_no_deps_fails_before_download(self):
        self.assertNotEqual(self.run_installer('--no-deps', FAKE_MISSING='1').returncode, 0)
        self.assertEqual(self.events(), [])

    def test_install_only_does_not_activate(self):
        self.assertEqual(self.run_installer('--install-only').returncode, 0)
        self.assertEqual(self.events()[-1], 'install_kde.py install')

    def test_conflicting_modes_rejected(self):
        self.assertEqual(self.run_installer('--check', '--prepare').returncode, 2)
        self.assertEqual(self.events(), [])

    def test_qdbus_path_fallback(self):
        with patch.object(install_kde.shutil, 'which', side_effect=lambda p: p if p == '/usr/lib/qt6/bin/qdbus' else None):
            self.assertEqual(install_kde.qdbus_command(), '/usr/lib/qt6/bin/qdbus')

    def test_distro_package_mapping(self):
        for distro, like, manager, package in [
            ('cachyos', 'arch', 'pacman', 'pyside6'),
            ('fedora', '', 'dnf', 'python3-pyside6'),
            ('ubuntu', 'debian', 'apt-get', 'python3-pyside6.qtquick')]:
            command = 'source tools/dependencies.sh; select_package_manager "$1" "$2"; MISSING=(qt qdbus xdg); packages_for_missing; printf "%s\\n" "$PACKAGE_MANAGER" "${PACKAGES[@]}"'
            result = subprocess.run(['bash', '-c', command, 'test', distro, like], cwd=ROOT,
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout.splitlines()[0], manager)
            self.assertIn(package, result.stdout.splitlines())
            self.assertIn('xdg-utils', result.stdout.splitlines())


if __name__ == '__main__':
    unittest.main()
