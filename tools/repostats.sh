#!/bin/sh
set -eu

# Report Markdown and source-code line counts for the repository's durable
# working groups. Generated Python caches and non-source data are ignored.

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

sum_markdown() {
    find "$@" \
        -type d \( -name .git -o -name __pycache__ \) -prune -o \
        -type f -name '*.md' -exec awk '{ total += 1 } END { print total + 0 }' {} + \
        | awk '{ total += $1 } END { print total + 0 }'
}

sum_source() {
    find "$@" \
        -type d \( -name .git -o -name __pycache__ \) -prune -o \
        -type f \( \
            -name '*.py' -o -name '*.sh' -o -name '*.lua' -o \
            -name '*.js' -o -name '*.ts' -o -name '*.tsx' -o \
            -name '*.jsx' -o -name '*.c' -o -name '*.h' -o \
            -name '*.cpp' -o -name '*.hpp' -o -name '*.html' -o \
            -name '*.css' -o -name '*.sql' -o \
            \( ! -name '*.*' -a -perm -111 \) \
        \) -exec awk '{ total += 1 } END { print total + 0 }' {} + \
        | awk '{ total += $1 } END { print total + 0 }'
}

sum_tools_source() {
    find "$root/tools" \
        -type d \( -name .git -o -name __pycache__ \) -prune -o \
        -type f ! -name 'pi-test*.sh' \( \
            -name '*.py' -o -name '*.sh' -o -name '*.lua' -o \
            -name '*.js' -o -name '*.ts' -o -name '*.tsx' -o \
            -name '*.jsx' -o -name '*.c' -o -name '*.h' -o \
            -name '*.cpp' -o -name '*.hpp' -o -name '*.html' -o \
            -name '*.css' -o -name '*.sql' -o \
            \( ! -name '*.*' -a -perm -111 \) \
        \) -exec awk '{ total += 1 } END { print total + 0 }' {} + \
        | awk '{ total += $1 } END { print total + 0 }'
}

report_group() {
    label=$1
    shift
    printf '%s\n' "$label"
    printf '  source code: %s\n' "$(sum_source "$@")"
    printf '  Markdown:    %s\n' "$(sum_markdown "$@")"
}

report_group 'src' "$root/src"
report_group 'docs' "$root/docs"

# Pi test scripts live in tools but belong to the tests total. Keep them out
# of the tools total so every line is counted exactly once.
printf '%s\n' 'tools'
printf '  source code: %s\n' "$(sum_tools_source)"
printf '  Markdown:    %s\n' "$(sum_markdown "$root/tools")"
printf '%s\n' 'tests (including tools/pi-test*.sh)'
printf '  source code: %s\n' "$(sum_source "$root/tests" "$root/tools"/pi-test*.sh)"
printf '  Markdown:    %s\n' "$(sum_markdown "$root/tests")"

report_group 'history' "$root/history"
