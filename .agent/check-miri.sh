#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
TOOLCHAIN="${JSONMODEM_MEMORY_TOOLCHAIN:-nightly}"
CASES="${JSONMODEM_SAFETY_CASES:-32}"
MODE="${1:-all}"
if [[ "$MODE" != all && "$MODE" != targeted ]]; then
    echo "Usage: $0 [all|targeted]" >&2
    exit 1
fi
if [[ ! "$CASES" =~ ^[1-9][0-9]*$ ]]; then
    echo "JSONMODEM_SAFETY_CASES must be a positive integer" >&2
    exit 1
fi
rustc "+$TOOLCHAIN" -vV
cargo "+$TOOLCHAIN" miri setup
if [[ "$MODE" == all ]]; then
    MIRIFLAGS="-Zmiri-env-set=JSONMODEM_SAFETY_CASES=$CASES" \
        cargo "+$TOOLCHAIN" miri nextest run --workspace --profile default-miri \
        --exclude jsonmodem-fuzz --exclude jsonmodem-py
fi
for model in stacked tree; do
    for seed in 0 1 2; do
        export MIRIFLAGS="-Zmiri-seed=$seed -Zmiri-env-set=JSONMODEM_SAFETY_CASES=$CASES"
        if [[ "$model" == tree ]]; then
            MIRIFLAGS+=" -Zmiri-tree-borrows"
        fi
        echo "Miri model=$model execution_seed=$seed generated_cases=$CASES"
        cargo "+$TOOLCHAIN" miri test -p jsonmodem --lib memory_safety -- --nocapture
        cargo "+$TOOLCHAIN" miri test -p jsonmodem --test memory_safety -- --nocapture
        cargo "+$TOOLCHAIN" miri test -p jsonmodem-py-validation fixed_offsets -- --nocapture
    done
    echo "Miri model=$model execution_seed=2 without cached-zipper"
    cargo "+$TOOLCHAIN" miri test -p jsonmodem --no-default-features \
        --lib backend::std::value_zipper::tests -- --nocapture
done

if [[ "$(uname -m)" == x86_64 ]]; then
    for features in \
        "+sse4.2,-avx2,-avx512f,-avx512bw,-avx512vbmi,-avx512vbmi2" \
        "+sse4.2,+avx2,-avx512f,-avx512bw,-avx512vbmi,-avx512vbmi2" \
        "+sse4.2,+avx2,+avx512f,+avx512bw,+avx512vbmi,+avx512vbmi2"; do
        echo "Miri model=tree execution_seed=1 target_features=$features"
        MIRIFLAGS="-Zmiri-tree-borrows -Zmiri-seed=1" \
            RUSTFLAGS="-C target-feature=$features" \
            cargo "+$TOOLCHAIN" miri test -p jsonmodem-py-validation -- --nocapture
    done
fi
