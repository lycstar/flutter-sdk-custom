#!/usr/bin/env python3
"""Complete and validate the Android ARM64 SDK distribution before publishing."""
import argparse
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import urllib.request
import zipfile


def validate_snapshot(path):
    data = path.read_bytes()
    if data[:5] != b'\x7fELF\x02' or data[5] != 1 or struct.unpack_from('<H', data, 18)[0] != 183:
        raise ValueError(f'{path}: expected little-endian AArch64 ELF64')
    if not os.access(path, os.X_OK):
        raise ValueError(f'{path}: not executable')
    headers = subprocess.check_output(['readelf', '-lW', str(path)], text=True)
    if '/system/bin/linker64' not in headers:
        raise ValueError(f'{path}: expected Android bionic interpreter, not glibc')
    dynamic = subprocess.check_output(['readelf', '-dW', str(path)], text=True)
    if 'libc.so.6' in dynamic or 'libstdc++.so.6' in dynamic:
        raise ValueError(f'{path}: desktop Linux dependency')


def complete(sdk, build_root, storage='https://storage.googleapis.com'):
    engine = (sdk / 'bin/internal/engine.version').read_text().strip()
    cache = sdk / 'bin/cache'
    artifacts = cache / 'artifacts/engine'
    for mode in ('profile', 'release'):
        snapshot = build_root / f'engine/src/out/android_{mode}_arm64/gen_snapshot'
        validate_snapshot(snapshot)
        destination = artifacts / f'android-arm64-{mode}'
        # These are target engine files, not host executables. Keep them pinned
        # to precisely the engine revision used to build gen_snapshot.
        url = f'{storage}/flutter_infra_release/flutter/{engine}/android-arm64-{mode}/artifacts.zip'
        with tempfile.TemporaryDirectory() as temporary:
            archive = Path(temporary) / 'artifacts.zip'
            print(f'Downloading {url}', flush=True)
            urllib.request.urlretrieve(url, archive)
            destination.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(archive) as source:
                for member in source.infolist():
                    target = (destination / member.filename).resolve()
                    if not target.is_relative_to(destination.resolve()):
                        raise ValueError(f'Unsafe archive entry: {member.filename}')
                source.extractall(destination)
        if not (destination / 'flutter.jar').is_file():
            raise ValueError(f'Missing Android engine flutter.jar: {destination}')
        host = destination / 'linux-arm64'
        host.mkdir(parents=True, exist_ok=True)
        shutil.copy2(snapshot, host / 'gen_snapshot')
        validate_snapshot(host / 'gen_snapshot')
    # Flutter's upstream Linux list assumes x64 host tools. Point ARM64 hosts
    # at the bundled bionic compilers, never at desktop glibc downloads.
    tools_cache = sdk / 'packages/flutter_tools/lib/src/flutter_cache.dart'
    text = tools_cache.read_text()
    start = text.index('class AndroidGenSnapshotArtifacts ')
    method = text.index('  List<List<String>> getBinaryDirs() {', start)
    insert = text.index('\n', method) + 1
    text = text[:insert] + """    if (_platform.isLinux && cache.getHostPlatformArchName() == 'arm64') {
      return <List<String>>[
        <String>['android-arm64-profile/linux-arm64', 'android-arm64-profile/linux-arm64.zip'],
        <String>['android-arm64-release/linux-arm64', 'android-arm64-release/linux-arm64.zip'],
      ];
    }
""" + text[insert:]
    tools_cache.write_text(text)
    (cache / 'android-sdk.stamp').write_text(engine)
    # A tool snapshot produced before modifying flutter_tools must be rebuilt.
    for name in ('flutter_tools.snapshot', 'flutter_tools.stamp'):
        (cache / name).unlink(missing_ok=True)
    print('Android ARM64 profile/release AOT distribution validated', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('sdk', type=Path)
    parser.add_argument('build_root', type=Path)
    args = parser.parse_args()
    complete(args.sdk, args.build_root)
