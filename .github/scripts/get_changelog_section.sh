#!/bin/sh

# Print the body of a version's section in the changelog, for use as release notes. Fail if the section
# is missing or empty, so that a version can't be released without any.

set -eu

if [ $# -lt 1 ] || [ $# -gt 2 ]; then
    echo "Usage: $0 VERSION [CHANGELOG_PATH]" >&2
    exit 2
fi

version=$1
changelog=${2:-CHANGELOG.md}

section=$(
    awk -v heading="## $version - " '
        index($0, heading) == 1 { in_section = 1; next }
        in_section && /^## / { exit }
        in_section && (started || NF) { started = 1; print }
    ' "$changelog"
)

if [ -z "$section" ]; then
    echo "$changelog has no notes for version $version" >&2
    exit 1
fi

printf '%s\n' "$section"
