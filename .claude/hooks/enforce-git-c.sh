#!/bin/bash
# PreToolUse hook for Bash commands.
# Blocks "cd <dir> && git ..." patterns and instructs Claude to use "git -C <dir> ..." instead.
# This avoids permission prompts when committing in sibling repositories because
# "git -C <dir> add ..." matches "Bash(git add:*)" while "cd <dir> && git add ..." does not.

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# Match: cd <path> && git <subcommand>
# Also match: cd <path> ; git <subcommand>
# Allow multiple && chains as long as git isn't after cd
if echo "$COMMAND" | grep -qP '^\s*cd\s+\S+.*[;&]+\s*git\s'; then
  cat >&2 <<'MSG'
Do not use "cd <dir> && git ..." or "cd <dir> ; git ...".
Use "git -C <dir> ..." instead. Each git subcommand should be a separate call:

  git -C <dir> add <files>
  git -C <dir> commit -m "message"
  git -C <dir> status

This matches the project's allowed Bash permission patterns and avoids interactive prompts.
MSG
  exit 2
fi

exit 0
