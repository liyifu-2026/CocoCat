#!/bin/bash
set -e

cleanup() {
    echo ""
    echo "=== Stopping ==="
    [ -n "$SERVER_PID" ] && kill $SERVER_PID 2>/dev/null
    [ -n "$VITE_PID" ] && kill $VITE_PID 2>/dev/null
    wait 2>/dev/null
    echo "Done."
    exit 0
}
trap cleanup SIGINT SIGTERM

echo "=== CocoCat v3 ==="
cd "$(dirname "$0")"

source .venv/bin/activate 2>/dev/null || {
    echo "ERROR: .venv not found. Run: python3 -m venv .venv && pip install -e ."
    exit 1
}

# Kill stale processes (graceful first, then force)
for port in 8000 5173 5174 5175; do
    fuser -k ${port}/tcp 2>/dev/null || true
done
sleep 1

# Load .env
set -a
[ -f .env ] && source .env
set +a

LOG_DIR="/tmp/cococat-logs"
mkdir -p $LOG_DIR

# Build backend args
unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY all_proxy no_proxy NO_PROXY
BACKEND_ARGS="--port ${COCOCAT_PORT:-8000} --db ${COCOCAT_DB:-cococat.db} --host 0.0.0.0"
if [ "${CUBE_SANDBOX:-}" = "1" ]; then
    BACKEND_ARGS="$BACKEND_ARGS --cube-sandbox"
    BACKEND_ARGS="$BACKEND_ARGS --cube-sandbox-template ${CUBESANDBOX_TEMPLATE_ID:-tpl-dedcd9373c3f49939f7feb9b}"
    echo "  CubeSandbox mode ON (template=${CUBESANDBOX_TEMPLATE_ID:-tpl-dedcd9373c3f49939f7feb9b})"
fi

# Start backend
echo -n "  Starting backend..."
python -m cococat $BACKEND_ARGS > $LOG_DIR/server.log 2>&1 &
SERVER_PID=$!

# Wait for backend to be ready (up to 10s)
for i in $(seq 1 20); do
    sleep 0.5
    if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
        echo " OK"
        break
    fi
    if [ $i -eq 20 ]; then
        echo " FAILED"
        echo "  tail -20 $LOG_DIR/server.log"
        tail -20 $LOG_DIR/server.log
        cleanup
    fi
done

# Start frontend dev server
echo -n "  Starting frontend..."
cd web-ui
npx vite --host > $LOG_DIR/vite.log 2>&1 &
VITE_PID=$!
cd ..

# Wait for frontend to be ready (up to 15s)
for i in $(seq 1 30); do
    sleep 0.5
    if curl -sf http://localhost:5173 > /dev/null 2>&1; then
        echo " OK"
        break
    fi
    if [ $i -eq 30 ]; then
        echo " WARN (may need more time)"
    fi
done

echo ""
echo "  Frontend : http://localhost:5173"
echo "  Backend  : http://localhost:8000"
echo "  Health   : http://localhost:8000/api/health"
echo "  Ctrl+C to stop"
echo "  Logs: $LOG_DIR/{server,vite}.log"
echo ""

wait
