#!/bin/bash
# notify.sh — play a sound to alert you
# Usage: bash notify.sh [message]

MSG="${1:-任务完成}"

# Generate a simple beep WAV if it doesn't exist
BEEP_FILE="/tmp/cococat-notify.wav"
if [ ! -f "$BEEP_FILE" ]; then
  # 双音叮咚：C5→E5，带衰减包络
  python3 -c "
import struct, math, wave
rate = 44100
total_dur = 0.35
f1, f2 = 523, 659  # C5, E5
switch_at = int(0.22 * rate)
total_frames = int(total_dur * rate)
samples = []
for i in range(total_frames):
    t = i / rate
    freq = f1 if i < switch_at else f2
    env = max(0, 1.0 - t / total_dur)  # linear decay
    v = int(28000 * env * math.sin(2 * math.pi * freq * t))
    samples.append(v)
f = wave.open('$BEEP_FILE', 'w')
f.setnchannels(1); f.setsampwidth(2); f.setframerate(rate)
f.writeframes(struct.pack('<' + 'h' * len(samples), *samples))
f.close()
" 2>/dev/null
fi

# Play
if command -v aplay &>/dev/null; then
  aplay -q "$BEEP_FILE" 2>/dev/null
elif command -v paplay &>/dev/null; then
  paplay "$BEEP_FILE" 2>/dev/null
elif command -v afplay &>/dev/null; then
  afplay "$BEEP_FILE" 2>/dev/null
fi

echo "🔔 $MSG"
