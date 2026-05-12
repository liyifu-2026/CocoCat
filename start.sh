#!/bin/bash
cleanup() {
    echo ""
    echo "=== Stopping ==="
    kill $SERVER_PID $VITE_PID 2>/dev/null
    wait $SERVER_PID $VITE_PID 2>/dev/null
    echo "Done."
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "=== CocoCat v2 ==="
cd "$(dirname "$0")"

# Kill stale processes
kill -9 $(lsof -ti:8000) 2>/dev/null || true
kill -9 $(lsof -ti:5173) 2>/dev/null || true
kill -9 $(lsof -ti:5174) 2>/dev/null || true
kill -9 $(lsof -ti:5175) 2>/dev/null || true

# Load .env
set -a
[ -f .env ] && source .env
set +a

LOG_DIR="/tmp/cococat-logs"
mkdir -p $LOG_DIR

# Start backend (single Python process)
python3 -m cococat --port 8000 > $LOG_DIR/server.log 2>&1 &
SERVER_PID=$!
sleep 2
if curl -s http://localhost:8000/api/health > /dev/null 2>&1; then
  echo "  Server ✅ (8000)"
else
  echo "  Server ❌ — tail -20 $LOG_DIR/server.log"
fi

# Start frontend dev server
cd web-ui
npx vite --host > $LOG_DIR/vite.log 2>&1 &
VITE_PID=$!
cd ..
sleep 2
if curl -s -o /dev/null -w "%{http_code}" http://localhost:5173 | grep -q 200; then
  echo "  Frontend ✅ (5173)"
else
  echo "  Frontend ⚠️ (5173) — tail -20 $LOG_DIR/vite.log"
fi

echo ""
echo "  http://localhost:5173"
echo "  Ctrl+C to stop"
echo "  Logs: $LOG_DIR/{server,vite}.log"

wait
