#!/bin/bash
cleanup() {
    echo ""
    echo "=== 停止所有服务 ==="
    kill $RUST_PID $PYTHON_PID $VITE_PID 2>/dev/null
    wait $RUST_PID $PYTHON_PID $VITE_PID 2>/dev/null
    echo "已停止"
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "=== CocoCat 启动 ==="
cd "$(dirname "$0")"

# 杀残留进程
kill -9 $(lsof -ti:3000) 2>/dev/null || true
kill -9 $(lsof -ti:8000) 2>/dev/null || true
echo "  端口已释放"

# 加载 .env（忽略注释和空行）
set -a
source .env
set +a

LOG_DIR="/tmp/cococat-logs"
mkdir -p $LOG_DIR

# 启动 Rust 后端
./target/debug/cococat > $LOG_DIR/rust.log 2>&1 &
RUST_PID=$!
sleep 2
if curl -s http://localhost:3000/api/health > /dev/null 2>&1; then
  echo "  Rust 后端 ✅ (3000)"
else
  echo "  Rust 后端 ❌ (3000) — tail -20 $LOG_DIR/rust.log"
fi

# 启动 Python 后端
uvicorn web.main:app --host 0.0.0.0 --port 8000 > $LOG_DIR/python.log 2>&1 &
PYTHON_PID=$!
sleep 2
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
  echo "  Python 后端 ✅ (8000)"
else
  echo "  Python 后端 ❌ (8000) — tail -20 $LOG_DIR/python.log"
fi

# 启动前端
cd web-ui
npx vite --host > $LOG_DIR/vite.log 2>&1 &
VITE_PID=$!
cd ..
sleep 2
if curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 | grep -q 200; then
  echo "  前端 ✅ (5173)"
else
  echo "  前端 ⚠️ (5173) — tail -20 $LOG_DIR/vite.log"
fi

echo ""
echo "  浏览器: http://localhost:5173"
echo "  密码: admin"
echo "  Ctrl+C 停止全部"
echo "  日志: $LOG_DIR/{rust,python,vite}.log"

wait
