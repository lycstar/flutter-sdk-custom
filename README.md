# flutter-sdk-custom

Cross-build recipes and CI for a self-hosted **Flutter SDK**
(`aarch64-linux-android`, Termux layout): the engine + dart-sdk + skia are
cross-compiled with gclient-pinned sources, then packaged with the Flutter
framework tools so the whole SDK runs on an Android device itself.

Not a fork of anything — the value here is entirely the version-pinned
configs (`versions/<version>/`), the patches, and the packaging scripts.

## How versions work (e.g. when 3.47.8 lands)

One directory per version: `versions/<version>/` = `build.toml` (flutter tag,
gclient file, patch paths) + the gclient file + `patches/`.
A new version = copy a directory and re-base the patches on the new engine
sources — that re-base is the only unavoidable manual step; everything else is
data-driven, no script or workflow changes. The workflow takes a `version`
input, copies that directory into place, builds, and publishes a release with
the same tag.

## Local build (the proven path — 3.47.7 was built this way)

Ubuntu machine: `bash linux-setup.sh` (once) → `bash linux-run.sh`
(idempotent, resumable; `PROXY=http://... bash linux-run.sh` if a proxy is
needed) → `python3 package.py`.
Host prerequisites: `~/ndk/android-ndk-r27c`, `~/depot_tools` (see
`linux-setup.sh`). Copy `versions/<version>/` into the repo root first
(see the workflow step for the exact commands).

## CI (experimental)

`.github/workflows/build-sdk.yml`: manual `workflow_dispatch`, takes the
version. A free 4-core runner needs ~6h for the engine and the host steps were
written for a local machine — first runs are expected to need calibration.
Until then the local Ubuntu path remains the production one.

## Credits

- [flutter/flutter](https://github.com/flutter/flutter) &
  [flutter/engine](https://github.com/flutter/engine) — Apache-2.0, the thing
  being built
- [termux/termux-packages](https://github.com/termux/termux-packages) — the
  sysroot libraries come from the Termux apt repositories
- [HomuHomu833](https://github.com/HomuHomu833) — bionic aarch64 NDK/SDK
  builds that run the toolchain on-device
- [Lzhiyong/android-sdk-tools](https://github.com/lzhiyong/android-sdk-tools)
  — the original proof that Android host tools can be rebuilt for Android

---

# 中文说明

自建 **Flutter SDK**（`aarch64-linux-android`，Termux 布局）的交叉编译配方与
CI：engine + dart-sdk + skia 用 gclient 钉版本交叉编译，再与框架层打包成
能在 Android 手机本机运行的完整 SDK。

不是任何仓的 fork —— 全部价值在 `versions/<版本>/` 的配置、补丁与打包脚本。

**版本模型**：一个版本一个目录；新版本（比如 3.47.8）= 拷目录 + 在新引擎
源码上重校补丁，其余全数据驱动，workflow 按版本入参构建并发同名 release。

**本机构建（现役路径，3.47.7 即此法产出）**：Ubuntu 上 `bash linux-setup.sh`
→ `bash linux-run.sh`（幂等断点续传）→ `python3 package.py`；宿主前置
`~/ndk/android-ndk-r27c`、`~/depot_tools`。

**CI（实验性）**：手动触发填版本号；免费 runner 编引擎约 6 小时，宿主步骤
首跑需校准，跑通前以本机路径为准。

**致谢**：[flutter/flutter](https://github.com/flutter/flutter) 与
[flutter/engine](https://github.com/flutter/engine)（Apache-2.0）、
[termux/termux-packages](https://github.com/termux/termux-packages)
（sysroot 库来源）、[HomuHomu833](https://github.com/HomuHomu833)
（bionic aarch64 NDK/SDK）、
[Lzhiyong/android-sdk-tools](https://github.com/lzhiyong/android-sdk-tools)
（Android 宿主工具可重建的最早实证）。
