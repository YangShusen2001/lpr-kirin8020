#!/usr/bin/env bash
# 构建包装（复刻 lpr-harmony/build.sh 的三个必要环境变量与两个陷阱规避）
set -e
unset NODE_OPTIONS
export DEVECO_HOME="<DEVECO_HOME>"
export DEVECO_SDK_HOME="<SDK>"
export NODE_HOME="<DEVECO_NODE>"
export JAVA_HOME='<JBR>'
export PATH="/d/IDE/DevEco_Studio/jbr/bin:$PATH"

PROJ="${1:-<REPO>/lpr-kirin8020/_hvigor_probe/LprDemo}"
shift || true
cd "$PROJ"
echo "PWD=$(pwd)"
echo "=== assembleHap ==="
"<DEVECO_NODE>/node.exe" \
  "<HVIGOR>/bin/hvigorw.js" \
  assembleHap --mode module -p product=default -p buildMode=debug --no-daemon "$@" 2>&1
echo "[hvigor rc=$?]"
echo "=== 产物 ==="
ls -la "$PROJ/entry/build/default/outputs/default/" 2>&1 || echo "(无 outputs 目录)"
