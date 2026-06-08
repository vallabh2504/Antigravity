#!/usr/bin/env bash
# Install the job-automation skill into your OpenClaw workspace.
# Usage:  bash install.sh
set -euo pipefail

SKILL_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
SKILLS_DIR="$WORKSPACE/skills"
LINK="$SKILLS_DIR/job-automation"

echo "Skill source : $SKILL_SRC"
echo "OpenClaw skills dir: $SKILLS_DIR"

mkdir -p "$SKILLS_DIR"

if [ -e "$LINK" ] && [ ! -L "$LINK" ]; then
  echo "ERROR: $LINK exists and is not a symlink. Move it aside first." >&2
  exit 1
fi
ln -sfn "$SKILL_SRC" "$LINK"
echo "Linked: $LINK -> $SKILL_SRC"

echo "Installing Python deps..."
pip install -r "$SKILL_SRC/requirements.txt"

# Seed config from examples if missing
[ -f "$SKILL_SRC/secrets.yml" ]        || cp "$SKILL_SRC/secrets.example.yml" "$SKILL_SRC/secrets.yml"
[ -f "$SKILL_SRC/master_resume.yml" ]  || cp "$SKILL_SRC/master_resume.example.yml" "$SKILL_SRC/master_resume.yml"

cat <<'EOF'

Done. Next:
  1. Edit skill/secrets.yml      (your details + Adzuna keys + resume PDF path)
  2. Edit skill/master_resume.yml (your real CV content)
  3. In OpenClaw, ask: "run the job search"   (verifies end-to-end)
  4. Then add an OpenClaw cron job to run it every morning (see SKILL.md > Cron).
EOF
