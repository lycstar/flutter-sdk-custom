#!/bin/bash
# Linux(Ubuntu 22.04)环境一次性引导:apt 依赖 + pip 依赖 + NDK r27c + depot_tools
# 幂等,可重复执行。直连不畅时:PROXY=http://<代理地址> bash linux-setup.sh
#
# apt 部分需要 root:可直接以 root 运行并传 --apt-only,
# 或以普通用户运行(能免密 sudo 则自动 sudo,否则有交互终端时 sudo 会提示输密码)。
set -e

APT_ONLY=0
NO_APT=0
for arg in "$@"; do
    case "$arg" in
        --apt-only) APT_ONLY=1 ;;
        --no-apt)   NO_APT=1 ;;
    esac
done

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if sudo -n true 2>/dev/null; then
        SUDO="sudo"
    elif [ "$NO_APT" -ne 1 ]; then
        echo '错误:无 root 权限。请先以 root 执行本脚本并加 --apt-only:' >&2
        echo '  sudo bash linux-setup.sh --apt-only' >&2
        echo '或已装过 apt 依赖则加 --no-apt 跳过 apt 段。' >&2
        exit 1
    fi
fi

if [ "$NO_APT" -ne 1 ]; then
    echo '==> apt 依赖'
    $SUDO apt update
    $SUDO apt install -y git curl python3-pip ninja-build cmake clang lld \
        bison gperf pkg-config patch unzip zip dpkg-dev rsync build-essential
fi

if [ "$APT_ONLY" -eq 1 ]; then
    echo '==> apt 部分完成(以 root 运行,跳过用户级步骤)'
    exit 0
fi

PROXY="${PROXY:-}"
if [ -n "$PROXY" ]; then
    export http_proxy="$PROXY" https_proxy="$PROXY"
fi

NDK_HOME="$HOME/ndk"
NDK_DIR="$NDK_HOME/android-ndk-r27c"
DEPOT_DIR="$HOME/depot_tools"
KIT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo '==> pip 依赖'
pip3 install --user -r "$KIT_DIR/requirements.txt" || pip3 install -r "$KIT_DIR/requirements.txt"
export PATH="$HOME/.local/bin:$PATH"

echo '==> Android NDK r27c'
if [ ! -d "$NDK_DIR" ]; then
    mkdir -p "$NDK_HOME"
    curl -fL --retry 3 --connect-timeout 15 \
        -o /tmp/android-ndk-r27c-linux.zip \
        https://dl.google.com/android/repository/android-ndk-r27c-linux.zip
    unzip -q /tmp/android-ndk-r27c-linux.zip -d "$NDK_HOME"
    rm -f /tmp/android-ndk-r27c-linux.zip
else
    echo 'NDK 已存在,跳过'
fi

echo '==> depot_tools'
if [ ! -d "$DEPOT_DIR/.git" ]; then
    git clone https://chromium.googlesource.com/chromium/tools/depot_tools.git "$DEPOT_DIR"
else
    echo 'depot_tools 已存在,跳过'
fi

echo '==> 环境引导完成'
echo "ANDROID_NDK=$NDK_DIR"
echo "PATH 需含: $DEPOT_DIR"
