# flutter-sdk-custom

Cross-build recipes and CI for a self-hosted **Flutter SDK** targeting
`aarch64-linux-android` (Termux layout). The engine, dart-sdk and skia
sources are fetched with gclient at pinned revisions, patched, cross-compiled
against a Termux sysroot, and packaged with the Flutter framework tools into
a complete SDK that runs on an Android device.

This repository is not a fork; its content consists of version-pinned
configuration (`versions/<version>/`), patches, and packaging scripts.

## Versioning

Each version lives in `versions/<version>/`, containing `build.toml` (the
flutter tag, the gclient file and the patch paths), the gclient file, and
`patches/`. Support for a new Flutter version is added by introducing a new
directory and re-basing the patches against the corresponding engine sources;
the scripts and the workflow remain unchanged. The workflow accepts the
version as an input, materialises that directory at the repository root,
builds, and publishes a release with the same tag.

## Build

Local (production path; 3.47.7 was produced this way): on Ubuntu, run
`bash linux-setup.sh` once, then `bash linux-run.sh` (idempotent and
resumable; set `PROXY=http://...` when a proxy is required), then
`python3 package.py`. Host prerequisites: `~/ndk/android-ndk-r27c` and
`~/depot_tools` (see `linux-setup.sh`). Materialise `versions/<version>/`
at the repository root first — the workflow contains the exact commands.

## Android APK support

The distribution supports an Android ARM64 host and Android ARM64 APK targets.
Release and profile `gen_snapshot` tools are built separately with Android target
semantics and the bionic Termux toolchain. Linux GTK snapshot generators are not
reused for Android. Packaging adds the matching official target engine artifacts
and validates the AArch64 ELF interpreter and target-tool compiler flags before
publishing. The bundled Flutter cache selects these host tools on Linux ARM64.
Use `flutter build apk --target-platform android-arm64`; other APK targets are
not included. CI checks build flags and distribution layout; release APK execution
still requires an ARM64 Android device test.

## CI

`.github/workflows/build-sdk.yml` provides a manual `workflow_dispatch`
workflow that takes the version as input. The engine build requires several
hours on a free hosted runner, and the host steps were written for a local
machine; initial runs may require calibration. Until then the local Ubuntu
path remains the production one.

## Credits

- [flutter/flutter](https://github.com/flutter/flutter) and
  [flutter/engine](https://github.com/flutter/engine) — Apache-2.0; the
  sources being built
- [mumumusuc/termux-flutter](https://github.com/mumumusuc/termux-flutter) —
  prior art for building Flutter natively in Termux
- [termux/termux-packages](https://github.com/termux/termux-packages) — the
  sysroot libraries are drawn from the Termux package repositories

---

# 中文说明

自建 **Flutter SDK**（`aarch64-linux-android`，Termux 布局）的交叉编译配方与
CI：engine、dart-sdk、skia 以 gclient 钉定版本拉取并打补丁，针对 Termux
sysroot 交叉编译，最后与框架层打包为可在 Android 设备本机运行的完整 SDK。

本仓库不是任何项目的 fork；内容为按版本钉定的配置（`versions/<版本>/`）、
补丁与打包脚本。

**版本模型**：每个版本一个目录，内含 `build.toml`（flutter tag、gclient
文件、补丁路径）、gclient 文件与 `patches/`。新增版本 = 新建目录并在对应
引擎源码上重校补丁；脚本与 workflow 不变。workflow 以版本为入参，将该目录
落到仓库根后构建，并以同名 tag 发布 release。

**构建**：生产路径为本机 Ubuntu——`bash linux-setup.sh`（一次）、
`bash linux-run.sh`（幂等、可断点续传，需要代理时设置 `PROXY`）、
`python3 package.py`；宿主前置为 `~/ndk/android-ndk-r27c` 与
`~/depot_tools`。构建前先将 `versions/<版本>/` 落到仓库根（workflow 中有
确切命令）。

**Android APK**：仅支持 Android ARM64 宿主和 ARM64 APK。release/profile 的
`gen_snapshot` 单独按 Android 目标及 bionic 工具链构建，不复用 Linux GTK 版本；
打包匹配的官方目标引擎，发布前校验 ELF 架构、解释器和编译参数。
使用 `flutter build apk --target-platform android-arm64`。设备端完整发布构建仍需真机验证。

**CI**：`build-sdk.yml` 提供手动触发的 workflow；引擎编译在免费 runner 上
需数小时，宿主步骤以本机为基准编写，首跑可能需要校准；校准完成前以本机
路径为准。

**致谢**：[flutter/flutter](https://github.com/flutter/flutter) 与
[flutter/engine](https://github.com/flutter/engine)（Apache-2.0，构建对象）、
[mumumusuc/termux-flutter](https://github.com/mumumusuc/termux-flutter)
（Termux 原生构建 Flutter 的先行项目）、
[termux/termux-packages](https://github.com/termux/termux-packages)
（sysroot 库来源）。
