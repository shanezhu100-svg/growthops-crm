#!/bin/sh
set -eu

# Vercel semantics: exit 0 = ignore this build; exit 1 = continue building.
# Fail safe: missing/invalid Git context always continues the Production build.
previous_sha="${VERCEL_GIT_PREVIOUS_SHA:-}"
if [ -z "${previous_sha}" ]; then
  echo "VERCEL_IGNORE_BUILD: previous deployment SHA unavailable; continue build"
  exit 1
fi
if ! git cat-file -e "${previous_sha}^{commit}" 2>/dev/null; then
  echo "VERCEL_IGNORE_BUILD: previous deployment commit unavailable; continue build"
  exit 1
fi
if ! git merge-base --is-ancestor "${previous_sha}" HEAD 2>/dev/null; then
  echo "VERCEL_IGNORE_BUILD: previous deployment is not an ancestor; continue build"
  exit 1
fi

changed_files="$(git diff --name-only "${previous_sha}" HEAD --)" || {
  echo "VERCEL_IGNORE_BUILD: diff failed; continue build"
  exit 1
}

if [ -z "${changed_files}" ]; then
  echo "VERCEL_IGNORE_BUILD: no changed files; skip build"
  exit 0
fi

all_nonruntime=1
while IFS= read -r file; do
  [ -n "${file}" ] || continue
  case "${file}" in
    .github/*|test_*.py|test_*.js|test_*.mjs|*.md)
      ;;
    *)
      all_nonruntime=0
      echo "VERCEL_IGNORE_BUILD: runtime-relevant change ${file}; continue build"
      break
      ;;
  esac
done <<EOF
${changed_files}
EOF

if [ "${all_nonruntime}" -eq 1 ]; then
  echo "VERCEL_IGNORE_BUILD: only CI/test/Markdown changes since last deployment; skip build"
  exit 0
fi
exit 1
