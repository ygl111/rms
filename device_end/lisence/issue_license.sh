#!/usr/bin/env bash
set -euo pipefail

# ============================================================
# 许可证签发脚本（Linux）
# 目标：只生成三字段许可证正文
#   1) exp         过期时间戳（Unix 秒）
#   2) max_devices 同时连接上限
#   3) mac         绑定服务器 MAC
#
# 输出文件：
#   payload.json   许可证正文
#   payload.sig    签名（二进制）
#   license.token  最终令牌（用于 tcp_gateway/config/license.env 的 LICENSE_TOKEN）
# ============================================================

if ! command -v openssl >/dev/null 2>&1; then
  echo "[ERROR] 未检测到 openssl，请先安装后再执行。"
  exit 1
fi

usage() {
  cat <<'EOF'
用法:
  bash issue_license.sh \
    --mac aa:bb:cc:dd:ee:ff \
    --exp 1784188800 \
    --max 500 \
    --priv /path/to/vendor_private.pem

或（推荐，给不熟悉时间戳的同事/厂商）:
  bash issue_license.sh \
    --mac aa:bb:cc:dd:ee:ff \
    --exp-utc "2026-12-31 23:59:59" \
    --max 500 \
    --priv /path/to/vendor_private.pem

参数说明:
  --mac   绑定的服务器MAC（小写、冒号分隔）
  --exp   过期时间戳（Unix秒）
  --exp-utc  过期UTC时间（例如: "2026-12-31 23:59:59"）
  --max   同时连接设备上限（正整数）
  --priv  厂商私钥路径（PEM）

可选参数:
  --outdir /path/to/output  输出目录（默认当前目录）

示例:
  bash issue_license.sh --mac aa:bb:cc:dd:ee:ff --exp 1784188800 --max 500 --priv ./vendor_private.pem
  bash issue_license.sh --mac aa:bb:cc:dd:ee:ff --exp-utc "2026-12-31 23:59:59" --max 500 --priv ./vendor_private.pem
EOF
}

MAC=""
EXP=""
EXP_UTC=""
MAX_DEV=""
PRIV_KEY=""
OUTDIR="$(pwd)"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mac)
      MAC="${2:-}"
      shift 2
      ;;
    --exp)
      EXP="${2:-}"
      shift 2
      ;;
    --exp-utc)
      EXP_UTC="${2:-}"
      shift 2
      ;;
    --max)
      MAX_DEV="${2:-}"
      shift 2
      ;;
    --priv)
      PRIV_KEY="${2:-}"
      shift 2
      ;;
    --outdir)
      OUTDIR="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] 未知参数: $1"
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$MAC" || -z "$MAX_DEV" || -z "$PRIV_KEY" ]]; then
  echo "[ERROR] 参数不完整。"
  usage
  exit 1
fi

if [[ -n "$EXP" && -n "$EXP_UTC" ]]; then
  echo "[ERROR] --exp 与 --exp-utc 只能二选一。"
  exit 1
fi

if [[ -z "$EXP" && -z "$EXP_UTC" ]]; then
  echo "[ERROR] 必须提供 --exp 或 --exp-utc 之一。"
  exit 1
fi

if [[ -n "$EXP_UTC" ]]; then
  if ! command -v date >/dev/null 2>&1; then
    echo "[ERROR] 未检测到 date 命令，无法解析 --exp-utc。"
    exit 1
  fi

  # 解析为 UTC Unix 秒。支持例如："2026-12-31 23:59:59" 或 "2026-12-31T23:59:59Z"
  EXP_PARSED="$(date -u -d "$EXP_UTC" +%s 2>/dev/null || true)"
  if [[ -z "$EXP_PARSED" || ! "$EXP_PARSED" =~ ^[0-9]+$ ]]; then
    echo "[ERROR] --exp-utc 解析失败，请使用可识别的UTC时间格式，例如: \"2026-12-31 23:59:59\""
    exit 1
  fi
  EXP="$EXP_PARSED"
  echo "[INFO] --exp-utc 已解析为 Unix 时间戳: $EXP (UTC: $EXP_UTC)"
fi

if [[ ! -f "$PRIV_KEY" ]]; then
  echo "[ERROR] 私钥文件不存在: $PRIV_KEY"
  exit 1
fi

if ! [[ "$EXP" =~ ^[0-9]+$ ]]; then
  echo "[ERROR] --exp 必须是 Unix 秒级时间戳。"
  exit 1
fi

if ! [[ "$MAX_DEV" =~ ^[1-9][0-9]*$ ]]; then
  echo "[ERROR] --max 必须是正整数。"
  exit 1
fi

# 简单MAC格式校验（严格 6 组十六进制）
if ! [[ "$MAC" =~ ^([0-9a-f]{2}:){5}[0-9a-f]{2}$ ]]; then
  echo "[ERROR] --mac 格式不合法，示例: aa:bb:cc:dd:ee:ff"
  exit 1
fi

mkdir -p "$OUTDIR"
PAYLOAD_FILE="$OUTDIR/payload.json"
SIG_FILE="$OUTDIR/payload.sig"
TOKEN_FILE="$OUTDIR/license.token"

echo "[INFO] 生成许可证正文: $PAYLOAD_FILE"
cat > "$PAYLOAD_FILE" <<EOF
{"exp":${EXP},"max_devices":${MAX_DEV},"mac":"${MAC}"}
EOF

echo "[INFO] 使用私钥签名（RSA-PSS-SHA256）"
openssl dgst -sha256 \
  -sigopt rsa_padding_mode:pss \
  -sigopt rsa_pss_saltlen:-1 \
  -sign "$PRIV_KEY" \
  -out "$SIG_FILE" \
  "$PAYLOAD_FILE"

echo "[INFO] 组装 license.token"
PAYLOAD_B64="$(openssl base64 -A -in "$PAYLOAD_FILE" | tr '+/' '-_' | tr -d '=')"
SIG_B64="$(openssl base64 -A -in "$SIG_FILE" | tr '+/' '-_' | tr -d '=')"
echo "${PAYLOAD_B64}.${SIG_B64}" > "$TOKEN_FILE"

echo ""
echo "[DONE] 生成完成"
echo "  payload: $PAYLOAD_FILE"
echo "  sig:     $SIG_FILE"
echo "  token:   $TOKEN_FILE"
echo ""
echo "[NEXT] 将 license.token 内容填入 device_end/tcp_gateway/config/license.env:"
echo "  LICENSE_REQUIRED=true"
echo "  LICENSE_TOKEN=<license.token整行内容>"
