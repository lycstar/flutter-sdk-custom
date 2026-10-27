#!/bin/bash
# 同步本目录到 Linux 工作区(~/ftb)并启动构建(clone → sync → patch → sysroot → gn → ninja → deb)
# 要求:~/ndk/android-ndk-r27c、~/depot_tools(见 linux-setup.sh)
# 幂等,中断后重跑即断点续传。需要代理时:PROXY=http://<代理地址> bash linux-run.sh
set -e -o pipefail

PROXY="${PROXY:-}"
if [ -n "$PROXY" ]; then
    export http_proxy="$PROXY" https_proxy="$PROXY"
    # 本机回环不走代理(dart VM service / DDS 等本地服务会被代理截断)
    export NO_PROXY="127.0.0.1,localhost" no_proxy="127.0.0.1,localhost"
fi

SRC="$(cd "$(dirname "$0")" && pwd)"
WS="$HOME/ftb"

# 已在工作区内则直接构建;否则(如从挂载盘/共享目录运行)先拷贝进 Linux 原生文件系统
if [ "$SRC" != "$WS" ]; then
    mkdir -p "$WS"
    # flutter/ 与 sysroot/ 是重量级工作产物,rsync 时排除(且 --delete 不动被排除目录)
    rsync -a --delete --exclude 'flutter/' --exclude 'sysroot/' --exclude '*.log' "$SRC/" "$WS/"
fi

# 行尾兜底规范化(Windows 侧编辑可能带入 CRLF,会破坏 git apply / bash)
find "$WS" -maxdepth 2 -type f \
    \( -name '*.py' -o -name '*.sh' -o -name '*.toml' -o -name '*.patch' \
       -o -name '*.yaml' -o -name 'requirements.txt' -o -name '.gclient347' \) \
    -exec sed -i 's/\r$//' {} +

export ANDROID_NDK="$HOME/ndk/android-ndk-r27c"
export PATH="$HOME/depot_tools:$HOME/.local/bin:$PATH"

cd "$WS"
python3 build.py 2>&1 | tee -a build.log
