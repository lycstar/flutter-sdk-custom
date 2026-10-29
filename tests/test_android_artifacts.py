from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from android_artifacts import complete, validate_snapshot


class AndroidArtifactsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def snapshot(self, path, machine=183):
        path.parent.mkdir(parents=True, exist_ok=True)
        data = bytearray(64)
        data[:6] = b'\x7fELF\x02\x01'
        struct.pack_into('<H', data, 18, machine)
        path.write_bytes(data)
        path.chmod(0o755)
        return path

    def test_rejects_x64_and_glibc_compilers(self):
        with self.assertRaisesRegex(ValueError, 'AArch64'):
            validate_snapshot(self.snapshot(self.root / 'x64', 62))
        with patch('android_artifacts.subprocess.check_output', return_value='/lib/ld-linux-aarch64.so.1'):
            with self.assertRaisesRegex(ValueError, 'bionic'):
                validate_snapshot(self.snapshot(self.root / 'arm64'))

    def test_distribution_has_both_bionic_compilers_and_target_engines(self):
        sdk = self.root / 'sdk'
        engine = sdk / 'bin/internal/engine.version'
        engine.parent.mkdir(parents=True)
        engine.write_text('pinned-engine')
        tools = sdk / 'packages/flutter_tools/lib/src/flutter_cache.dart'
        tools.parent.mkdir(parents=True)
        tools.write_text('class AndroidGenSnapshotArtifacts {\n  List<List<String>> getBinaryDirs() {\n    return [];\n  }\n}')
        build = self.root / 'build'
        for mode in ('profile', 'release'):
            self.snapshot(build / f'engine/src/out/android_{mode}_arm64/gen_snapshot')
        urls = []

        def download(url, destination):
            urls.append(url)
            with zipfile.ZipFile(destination, 'w') as output:
                output.writestr('flutter.jar', 'engine jar')

        def readelf(command, **kwargs):
            return '/system/bin/linker64' if '-lW' in command else 'NEEDED libc.so'

        with patch('android_artifacts.urllib.request.urlretrieve', side_effect=download), \
             patch('android_artifacts.subprocess.check_output', side_effect=readelf):
            complete(sdk, build)
        self.assertEqual(len(urls), 2)
        for mode in ('profile', 'release'):
            self.assertIn(f'pinned-engine/android-arm64-{mode}/artifacts.zip', urls[['profile', 'release'].index(mode)])
            base = sdk / f'bin/cache/artifacts/engine/android-arm64-{mode}'
            self.assertTrue((base / 'flutter.jar').exists())
            self.assertTrue((base / 'linux-arm64/gen_snapshot').exists())
        self.assertEqual((sdk / 'bin/cache/android-sdk.stamp').read_text(), 'pinned-engine')
        self.assertIn("cache.getHostPlatformArchName() == 'arm64'", tools.read_text())



if __name__ == '__main__':
    unittest.main()
