#!/bin/sh
# Merge translations into the row files and check the villager text.
#   sh tools/refresh.sh            (run after agents finish, before a build)
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT" || exit 1
python tools/slices.py apply | tail -1
python tools/fix_names.py | tail -1
python tools/slices.py apply | tail -1          # names fixed in done/ reach the rows
python tools/auto_space.py | tail -1            # spaces after pauses (needs the current text)
python tools/slices.py apply | tail -1
for c in M0 M1 M2; do
  [ -f "work/translation/en/rows/${c}_C_${c}.STC.json" ] || continue
  python tools/check.py $c > "work/translation/en/reports/check_$c.txt"
  echo "$c: $(tail -1 work/translation/en/reports/check_$c.txt)"
done
python tools/story_check.py > work/translation/en/reports/check_story.txt
echo "story: $(tail -1 work/translation/en/reports/check_story.txt)"
