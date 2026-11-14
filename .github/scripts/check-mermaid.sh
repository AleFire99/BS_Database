#!/usr/bin/env bash
# Render every ```mermaid block of all tracked *.md files; fail on any error.
set -uo pipefail

MERMAID_CLI_VERSION="12.2.0"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
# PUPPETEER_EXECUTABLE_PATH: use a preinstalled Chrome (the GitHub ubuntu runner has one).
if [ -n "${PUPPETEER_EXECUTABLE_PATH:-}" ]; then
  printf '{"args":["--no-sandbox"],"executablePath":"%s"}' "$PUPPETEER_EXECUTABLE_PATH" > "$work/puppeteer.json"
else
  echo '{"args":["--no-sandbox"]}' > "$work/puppeteer.json"
fi

fail=0
count=0
while IFS= read -r file; do
  rm -f "$work"/block-*.mmd
  awk -v dir="$work" '
    /^[[:space:]]*```mermaid[[:space:]]*$/ { n++; inb=1; out=sprintf("%s/block-%03d.mmd", dir, n); next }
    inb && /^[[:space:]]*```[[:space:]]*$/ { inb=0; close(out); next }
    inb { print > out }
  ' "$file"
  for block in "$work"/block-*.mmd; do
    [ -e "$block" ] || continue
    count=$((count + 1))
    idx="$(basename "$block" .mmd | sed 's/block-0*//')"
    if ! npx -y "@mermaid-js/mermaid-cli@${MERMAID_CLI_VERSION}" \
      -p "$work/puppeteer.json" -i "$block" -o "$work/out.svg" >"$work/log.txt" 2>&1; then
      echo "::error file=$file::mermaid block #$idx failed to render"
      echo "FAIL: $file block #$idx"
      cat "$work/log.txt"
      fail=1
    else
      echo "ok: $file block #$idx"
    fi
  done
done < <(git ls-files '*.md')

echo "Checked $count mermaid block(s)."
exit $fail
