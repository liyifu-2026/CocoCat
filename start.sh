#!/bin/bash
set -e

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
kill -9 $(lsof -ti:8080) 2>/dev/null || true
echo "  端口已释放"

# 加载 .env
export JWT_SECRET=$(grep JWT_SECRET .env | cut -d= -f2)

# 启动 Rust 后端
JWT_SECRET=$JWT_SECRET ./target/debug/cococat > /dev/null 2>&1 &
RUST_PID=$!
sleep 2
echo "  Rust 后端 ✅ (3000)"

# 启动 Python 后端
JWT_SECRET=$JWT_SECRET uvicorn web.main:app --host 0.0.0.0 --port 8080 > /dev/null 2>&1 &
PYTHON_PID=$!
sleep 2
echo "  Python 后端 ✅ (8080)"

# 启动前端
cd web-ui
npx vite --host > /dev/null 2>&1 &
VITE_PID=$!
cd ..
sleep 2
echo "  前端 ✅ (5173)"

echo ""
echo "  浏览器: http://localhost:5173"
echo "  密码: admin"
echo "  Ctrl+C 停止全部"

wait
