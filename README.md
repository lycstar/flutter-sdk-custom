# flutter-sdk-custom

sparrow 自建 Flutter SDK(aarch64-linux-android, Termux 布局)的配方仓:
engine + dart-sdk + skia 交叉编译(Ubuntu 端, gclient 钉版本), 外加框架层打包。
不是 fork —— 我们的全部价值在 `patches/` 与打包脚本里。

## 本机构建(现役路径, 已验证 3.47.7)

Ubuntu + 7900X3D/64G: `bash linux-setup.sh`(一次性) → `bash linux-run.sh`
(幂等断点续传; 需要代理时 `PROXY=http://... bash linux-run.sh`) →
`python3 package.py`(打包) → 挂到本仓 Release。
宿主前置: `~/ndk/android-ndk-r27c`、`~/depot_tools`(见 linux-setup.sh)。

## CI(实验性)

`.github/workflows/build-sdk.yml`: 免费 runner 4 核编引擎 6h 起,
宿主脚本面向本机编写, runner 上首跑需校准 —— 未跑通前现役路径仍是本机。
