#!/usr/bin/env bash
# PostToolUse hook: run `marimo check` on edited marimo notebooks and feed
# any problems back to Claude (exit 2 = stderr is shown to the model).
f=$(jq -r '.tool_input.file_path // .tool_response.filePath // empty')
case "$f" in
  */notebooks/*.py) ;;
  *) exit 0 ;;
esac
grep -q '^app = marimo.App' "$f" 2>/dev/null || exit 0
if ! out=$(cd "${CLAUDE_PROJECT_DIR:-.}" && uv run -q --with-requirements "${CLAUDE_PROJECT_DIR:-.}/requirements.txt" marimo check "$f" 2>&1); then
  echo "marimo check failed for $f:" >&2
  echo "$out" >&2
  exit 2
fi
