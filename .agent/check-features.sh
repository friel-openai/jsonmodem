#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Select only the core package. Workspace dependents can re-enable defaults.
for features in none serde cached-zipper cached-zipper,serde simd simd,serde cached-zipper,simd cached-zipper,simd,serde; do
    args=(--no-default-features)
    if [[ "$features" != none ]]; then
        args+=(--features "$features")
    fi
    echo "Core features: $features"
    cargo test -p jsonmodem --locked "${args[@]}"
    cargo clippy -p jsonmodem --all-targets --locked "${args[@]}" -- -D warnings
    RUSTDOCFLAGS="-D warnings" cargo doc -p jsonmodem --no-deps --locked "${args[@]}"
done
