#!/bin/sh
# Stop the emulator, build, boot the new disc (optionally from a state of the same build).
#   sh tools/test.sh <version> [build args...]
ROOT=$(cd "$(dirname "$0")/.." && pwd)
V=$1; shift
E="powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ROOT/tools/emu.ps1"
$E stop >/dev/null
sleep 2
rm -f "$ROOT/work/emulator/duckstation/savestates/SLPS-01932_resume.sav"
python "$ROOT/tools/build.py" --version "$V" "$@" || exit 1
$E start "$ROOT/work/output/$V/Vampir (English v$V).cue" >/dev/null
echo booted $V
