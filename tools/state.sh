#!/bin/sh
# Snapshot the running emulator into work/ui/states/<name>.sav (stop -> resume state -> restart from it).
#   sh tools/state.sh <name> [cue]
ROOT=$(cd "$(dirname "$0")/.." && pwd)
CUE=${2:-"$ROOT/Vampir - Kyuuketsuki Densetsu (Japan).cue"}
E="powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ROOT/tools/emu.ps1"
$E stop >/dev/null
sleep 2
cp "$ROOT/work/emulator/duckstation/savestates/SLPS-01932_resume.sav" "$ROOT/work/ui/states/$1.sav"
$E start "$CUE" -StateFile "$ROOT/work/ui/states/$1.sav" >/dev/null
sleep 2
echo "saved $1"
