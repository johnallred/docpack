#!/usr/bin/env bash
# Cold-start test for the quickstart tutorial.
#
# Every other check in this repository runs against the tree as it exists, with
# dependencies already installed. This one starts from an empty directory and a
# fresh virtual environment, installs the package the way a reader would, and
# executes the tutorial's commands in order.
#
# It exists to catch the most common documentation failure there is: a
# quickstart that works on the author's machine because of something they
# installed months ago and forgot about.
#
# Usage:  scripts/coldstart.sh
# Exit:   0 if a reader following the tutorial reaches the documented result.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

say() { printf '\n\033[1m==> %s\033[0m\n' "$1"; }

say "Cold environment at $WORK"
cd "$WORK"

say "Tutorial step 1: create a virtual environment and install"
python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --quiet "$REPO_ROOT"

say "Tutorial step 1: verify the CLI is on PATH"
docpack --help > /dev/null
echo "docpack --help works"

say "Tutorial step 2: create the documentation tree"
mkdir -p mydocs/how-to

cat > mydocs/index.md <<'PAGE'
---
title: Widget API
summary: A small API for managing widgets.
diataxis: explanation
audience: new-user
updated: 2026-10-26
---

# Widget API

The Widget API lets you create, list, and retire widgets.

## Concepts

A widget has an identifier and a state. States are `active` and `retired`.
PAGE

cat > mydocs/how-to/create-a-widget.md <<'PAGE'
---
title: Create a widget
summary: Create a widget and confirm it exists.
diataxis: how-to
audience: developer
updated: 2026-10-26
---

# Create a widget

Send a POST request to the widgets endpoint.

## Confirm it worked

List the widgets and check that yours appears.
PAGE

say "Tutorial step 3: pack it"
OUTPUT="$(docpack mydocs --out dist --site-name "Widget API" --site-url "https://widgets.example")"
echo "$OUTPUT"

# The tutorial tells the reader to expect exactly this line.
EXPECTED="packed 2 pages into 4 chunks -> dist"
if [[ "$OUTPUT" != "$EXPECTED" ]]; then
  echo "FAIL: tutorial promises '$EXPECTED' but got '$OUTPUT'" >&2
  exit 1
fi
echo "output matches what the tutorial promises"

say "Tutorial step 4: inspect the artifacts"
for f in llms.txt chunks.jsonl llms-full.txt; do
  test -s "dist/$f" || { echo "FAIL: dist/$f missing or empty" >&2; exit 1; }
  echo "dist/$f present"
done
grep -q "^# Widget API" dist/llms.txt || { echo "FAIL: llms.txt has no H1" >&2; exit 1; }
grep -q "## How-to guides" dist/llms.txt || { echo "FAIL: llms.txt not grouped" >&2; exit 1; }
python3 -c "
import json,sys
rows=[json.loads(l) for l in open('dist/chunks.jsonl')]
assert len(rows)==4, f'expected 4 chunks, got {len(rows)}'
assert {r['diataxis'] for r in rows}=={'explanation','how-to'}
print('chunks.jsonl has the documented shape')
"

replace_diataxis() {
  python3 - "$1" "$2" <<'PY'
from pathlib import Path
import sys

path = Path("mydocs/how-to/create-a-widget.md")
old, new = f"diataxis: {sys.argv[1]}", f"diataxis: {sys.argv[2]}"
text = path.read_text(encoding="utf-8")
if text.count(old) != 1:
    raise SystemExit(f"expected exactly one {old!r} in {path}")
path.write_text(text.replace(old, new), encoding="utf-8")
PY
}

say "Tutorial step 5: break it on purpose"
replace_diataxis how-to blog-post
if docpack mydocs --check > /dev/null 2>&1; then
  echo "FAIL: tutorial says an invalid diataxis fails validation, but it passed" >&2
  exit 1
fi
echo "invalid content model is rejected, as the tutorial promises"

replace_diataxis blog-post how-to
docpack mydocs --check > /dev/null
echo "restored page passes again"

# The generator is checked here, from a cold environment, rather than only in
# the unit suite. A contributor's first real use of `docpack new` is on a
# machine where nothing is set up, which is exactly the situation the unit
# tests cannot reproduce.
say "Generator: every type produces a page the validator accepts"
mkdir -p gendocs
for type in tutorial how-to reference explanation; do
  docpack new "$type" --docs gendocs \
    --title "Generated $type page" \
    --summary "A generated $type page." > /dev/null
done
docpack gendocs --check > /dev/null
echo "all four generated pages conform"

# A title containing a colon broke the first version of the generator, which
# assembled YAML by hand. Kept as a cold-start case because the failure was in
# serialization rather than in logic.
docpack new reference --docs gendocs --title "Errors: a reference" > /dev/null
docpack gendocs --check > /dev/null
echo "a title containing a colon still produces valid front matter"

if docpack new how-to --docs gendocs --title "Generated how-to page" > /dev/null 2>&1; then
  echo "FAIL: the generator overwrote an existing page" >&2
  exit 1
fi
echo "an existing page is not overwritten"

docpack gendocs --out gendist > /dev/null
test -s gendist/llms.txt || { echo "FAIL: generated tree did not pack" >&2; exit 1; }
echo "a tree built entirely by the generator packs cleanly"

say "COLD START PASSED: a reader following the tutorial reaches the documented result"
