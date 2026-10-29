#!/usr/bin/env python3
# Vendored from mumumusuc/termux-flutter (GPL-3.0), adapted for Flutter 3.47.7:
#  - tomllib fallback to tomli on Python 3.10 (Ubuntu 22.04)
#  - patches are applied inside __call__ (upstream relied on .gclient custom_hooks,
#    which .gclient347 intentionally does not define)
#  - patch() is idempotent: skips when the patch is already applied
#  - configure() honors the ndk api from build.toml

import os
import sys
import git
import fire
import yaml
import utils
import shutil
import subprocess

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

from loguru import logger
from pathlib import Path
from sysroot import Sysroot
from package import Package


class GitProgress(git.RemoteProgress):
    def update(self, op_code, cur_count, max_count=None, message=''):
        logger.trace(f"cloning {cur_count}/{max_count} {message}")


@utils.record
class Build:
    @utils.recordm
    def __init__(self, conf='build.toml'):
        path = Path(__file__).parent
        conf = path/conf

        with open(conf, 'rb') as f:
            cfg = tomllib.load(f)

        ndk = cfg['ndk'].get('path') or os.environ.get('ANDROID_NDK')
        api = cfg['ndk'].get('api')
        tag = cfg['flutter'].get('tag')
        repo = cfg['flutter'].get('repo')
        root = cfg['flutter'].get('path')
        arch = cfg['build'].get('arch')
        mode = cfg['build'].get('runtime')
        gclient = cfg['build'].get('gclient')
        sysroot = cfg['sysroot']
        syspath = sysroot.pop('path')
        package = cfg['package'].get('conf')
        release = cfg['package'].get('path')
        patches = cfg.get('patch')

        if not ndk:
            raise ValueError('neither ndk path nor ANDROID_NDK is set')
        if not tag:
            raise ValueError('require flutter tag')

        self.tag = tag
        self.api = api or 26
        self.conf = conf
        # TODO: detect host
        self.host = 'linux-x86_64'
        self.repo = repo or 'https://github.com/flutter/flutter'
        self.arch = arch or 'arm64'
        self.mode = mode or 'debug'
        self.sysroot = Sysroot(path=path/syspath, **sysroot)
        self.root = path/root
        self.gclient = path/gclient
        self.release = path/release
        self.toolchain = Path(ndk, f'toolchains/llvm/prebuilt/{self.host}')

        if not self.release.parent.is_dir():
            raise ValueError(f'bad release path: "{release}"')

        with open(path/package, 'rb') as f:
            self.package = yaml.safe_load(f)

        if isinstance(patches, dict):
            self.patches = {}

            def patch(key):
                return lambda: self.patch(**self.patches[key])

            for k, v in patches.items():
                self.patches[k] = {
                    'file': path/v['file'],
                    'path': self.root/v['path']}
                self.__dict__[f'patch_{k}'] = patch(k)

    def config(self):
        info = (f'{k}\t: {v}' for k, v in self.__dict__.items() if k != 'package')
        logger.info('\n'+'\n'.join(info))

    def clone(self, *, url: str = None, tag: str = None, out: str = None):
        url = url or self.repo
        out = out or self.root
        tag = tag or self.tag
        progress = GitProgress()

        if utils.flutter_tag(out) == tag:
            logger.info('flutter exists, skip.')
            return
        elif os.path.isdir(out):
            logger.info(f'moving {out} to {out}.old ...')
            os.rename(out, f'{out}.old')
            return

        try:
            git.Repo.clone_from(
                url=url,
                to_path=out,
                progress=progress,
                branch=tag)
        except git.exc.GitCommandError:
            raise RuntimeError('\n'.join(progress.error_lines))

    def sync(self, *, cfg: str = None, root: str = None):
        cfg = cfg or self.gclient
        src = root or self.root

        shutil.copy(cfg, os.path.join(src, '.gclient'))
        cmd = ['gclient', 'sync', '-DR', '--no-history']
        subprocess.run(cmd, cwd=src, check=True, stdout=True, stderr=True)

    def patch(self, *, file, path):
        repo = git.Repo(path)
        try:
            repo.git.apply('--check', '--reverse', str(file))
            logger.info(f'patch already applied, skip: {file}')
            return
        except git.exc.GitCommandError:
            pass
        repo.git.apply([str(file)])
        logger.info(f'patched: {file}')

    def configure(
        self,
        arch: str,
        mode: str,
        api: int = None,
        root: str = None,
        sysroot: str = None,
        toolchain: str = None,
        android_aot: bool = False,
    ):
        api = api or self.api
        root = root or self.root
        sysroot = os.path.abspath(sysroot or self.sysroot.path)
        toolchain = os.path.abspath(toolchain or self.toolchain)
        cmd = [
            'vpython3',
            'engine/src/flutter/tools/gn',
            '--android' if android_aot else '--linux',
            '--android-cpu' if android_aot else '--linux-cpu', arch,
        ]
        # txt/BUILD.gn asserts is_linux when fontconfig is on, which --android
        # violates; gen_snapshot itself never links the fontconfig text stack.
        if not android_aot:
            cmd.append('--enable-fontconfig')
        cmd += [
            '--no-goma',
            '--no-backtrace',
            '--clang',
            '--no-lto',
            '--no-enable-unittests',
            '--no-build-embedder-examples',
            '--no-prebuilt-dart-sdk',
            '--target-toolchain', toolchain,
            '--runtime-mode', mode,
            '--no-build-glfw-shell',
            '--gn-args', 'symbol_level=0',
            '--gn-args', 'arm_use_neon=false',
            '--gn-args', 'arm_optionally_use_neon=true',
            '--gn-args', 'dart_include_wasm_opt=false',
            '--gn-args', 'dart_platform_sdk=false',
            '--gn-args', 'is_desktop_linux=false',
            '--gn-args', 'use_default_linux_sysroot=false',
            '--gn-args', 'skia_use_perfetto=false',
            '--gn-args', f'custom_sysroot="{sysroot}"',
            '--gn-args', 'is_termux=true',
            '--gn-args', f'is_termux_host={utils.__TERMUX__}',
            '--gn-args', f'termux_api_level={api}',
        ]
        subprocess.run(cmd, cwd=root, check=True, stdout=True, stderr=True)

    def build_android_aot(self, arch: str, mode: str):
        if arch != 'arm64' or mode not in ('profile', 'release'):
            raise ValueError('Android AOT distribution supports arm64 profile/release only')
        # GN also loads Android toolchain metadata; Android dependency downloads
        # are disabled in gclient, so expose the configured NDK at its expected path.
        android_config = self.root / 'engine/src/build/config/android/config.gni'
        import re
        match = re.search(r'android_ndk_version = "([^"]+)"', android_config.read_text())
        if match is None:
            raise RuntimeError('Cannot determine the engine Android NDK path')
        ndk_link = self.root / 'engine/src/flutter/third_party/android_tools/sdk/ndk' / match[1]
        ndk_link.parent.mkdir(parents=True, exist_ok=True)
        if not ndk_link.exists():
            ndk_link.symlink_to(self.toolchain.parents[3], target_is_directory=True)
        self.configure(arch=arch, mode=mode, android_aot=True)
        output = self.root / 'engine/src/out' / f'android_{mode}_{arch}'
        # Build with the default Termux toolchain, not the Linux x64 host toolchain.
        # target_os=android gives Dart the Android target ABI; is_termux keeps
        # the executable itself compatible with Android bionic.
        subprocess.run(['ninja', '-C', str(output),
                        'gen_snapshot'], check=True)
        commands = subprocess.check_output(
            ['ninja', '-C', str(output), '-t', 'commands', 'gen_snapshot'], text=True)
        if 'DART_TARGET_OS_ANDROID' not in commands or '--target=aarch64-linux-android' not in commands:
            raise RuntimeError('gen_snapshot must use Android target semantics and bionic ARM64 toolchain')
        if not (output / 'gen_snapshot').is_file():
            raise RuntimeError(f'Android AOT compiler missing: {output}')

    def build(self, arch: str, mode: str, root: str = None, jobs: int = None):
        root = root or self.root
        cmd = [
            'ninja', '-C', utils.target_output(root, arch, mode),
            'flutter',
        ]
        if jobs:
            cmd.append(f'-j{jobs}')
        subprocess.run(cmd, check=True, stdout=True, stderr=True)

    def debuild(self, arch: str, output: str = None, root: str = None, **conf):
        conf = conf or self.package
        root = root or self.root
        output = output or self.output(arch)

        pkg = Package(root=root, arch=arch, **conf)
        pkg.debuild(output=output)

    def output(self, arch: str):
        if self.release.is_dir():
            name = f'flutter_{self.tag}_{utils.termux_arch(arch)}.deb'
            return self.release/name
        else:
            return self.release

    def __call__(self):
        self.config()
        self.clone()
        self.sync()

        for k in self.patches:
            self.__dict__[f'patch_{k}']()

        for arch in self.arch:
            self.sysroot(arch=arch)
            for mode in self.mode:
                self.configure(arch=arch, mode=mode)
                self.build(arch=arch, mode=mode)
            for mode in ('profile', 'release'):
                self.build_android_aot(arch=arch, mode=mode)
            self.debuild(arch=arch, output=self.output(arch))


if __name__ == '__main__':
    logger.remove()
    logger.add(
        sys.stdout,
        diagnose=False,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <9}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>")
    )
    fire.Fire(Build())
