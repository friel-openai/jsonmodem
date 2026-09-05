#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
TOOLCHAIN="${JSONMODEM_MEMORY_TOOLCHAIN:-nightly}"
LOG="$(mktemp -t jsonmodem-string-miri.XXXXXX)"
STDERR="$(mktemp -t jsonmodem-string-miri-stderr.XXXXXX)"
trap 'rm -f "$LOG" "$STDERR"' EXIT
rustc "+$TOOLCHAIN" -vV
cargo "+$TOOLCHAIN" miri setup

# A successful empty test filter does not exercise the kernel.
run_checked() {
    local expected="$1"; shift
    if ! cargo "+$TOOLCHAIN" miri test --locked -p jsonmodem --lib "$@" \
        -- --nocapture 2>"$STDERR" | tee "$LOG"; then
        cat "$STDERR" >&2
        return 1
    fi
    cat "$STDERR" >&2
    [[ "$(grep -c '^test result:' "$LOG")" == 1 ]]
    grep -Fq "test result: ok. $expected passed; 0 failed; 0 ignored;" "$LOG"
}

for features in none simd; do
    args=(--no-default-features)
    expected=4
    native=false
    if [[ "$features" == simd ]]; then
        args+=(--features simd)
        native=true
    fi
    for model in stacked tree; do
        for seed in 0 1 2; do
            export MIRIFLAGS="-Zmiri-seed=$seed"
            if [[ "$model" == tree ]]; then
                MIRIFLAGS+=" -Zmiri-tree-borrows"
            fi
            echo "Miri string kernels: features=$features model=$model seed=$seed"
            run_checked "$expected" "${args[@]}" string_block
            grep -Fxq "string block SIMD=$native" "$STDERR"
            run_checked 1 "${args[@]}" \
                consecutive_short_escapes_preserve_errors_and_following_text
        done
    done
done
