#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FONT_PATH="$ROOT_DIR/games/static/games/fonts/materialdesignicons-webfont.woff2"
MAPPING_FILES=(
  "$ROOT_DIR/games/templates/base.html"
  "$ROOT_DIR/games/static/games/css/mdi-subset.css"
)

if ! command -v pyftsubset >/dev/null 2>&1; then
  echo "pyftsubset is required (pip install fonttools brotli zopfli)"
  exit 1
fi

if [[ ! -f "$FONT_PATH" ]]; then
  echo "Font not found: $FONT_PATH"
  exit 1
fi

tmp_codes="$(mktemp)"
tmp_unicodes="$(mktemp)"
tmp_output="$(mktemp "${TMPDIR:-/tmp}/mdi-subset.XXXXXX")"
trap 'rm -f "$tmp_codes" "$tmp_unicodes" "$tmp_output"' EXIT

for mapping_file in "${MAPPING_FILES[@]}"; do
  if [[ -f "$mapping_file" ]]; then
    rg --no-filename -o '\\F[0-9A-F]+' "$mapping_file" >> "$tmp_codes"
  fi
done

if [[ ! -s "$tmp_codes" ]]; then
  echo "No icon codepoints found in mapping files."
  exit 1
fi

sort -u "$tmp_codes" | sed 's/^\\//' | awk '{print "U+"$0}' > "$tmp_unicodes"
unicode_list="$(paste -sd, "$tmp_unicodes")"

if [[ -z "$unicode_list" ]]; then
  echo "Computed unicode list is empty."
  exit 1
fi

original_size="$(wc -c < "$FONT_PATH" | tr -d ' ')"
codepoint_count="$(wc -l < "$tmp_unicodes" | tr -d ' ')"

pyftsubset "$FONT_PATH" \
  --unicodes="$unicode_list" \
  --flavor=woff2 \
  --layout-features='*' \
  --desubroutinize \
  --output-file="$tmp_output"

mv "$tmp_output" "$FONT_PATH"
new_size="$(wc -c < "$FONT_PATH" | tr -d ' ')"

echo "Subset complete: $FONT_PATH"
echo "Codepoints kept: $codepoint_count"
echo "Size: $original_size -> $new_size bytes"
