# JsonModem Facet Streaming Adapter ExecPlan

This ExecPlan is a living document. Update `Progress`, `Surprises & Discoveries`, `Decision Log`, and `Outcomes & Retrospective` every time new information appears. Treat every section as guidance for a first-time contributor with no prior context.

## Purpose / Big Picture

`jsonmodem` already exposes raw parse events, buffered lending values, and tree snapshots, but it cannot yet hydrate user-defined `facet::Facet` structs directly from streaming JSON. We will add a `JsonModemFacet<T>` adapter that accepts arbitrarily chunked UTF-8, forwards parse events to a facet-aware runner, and lends `&T` snapshots after each `feed()` without cloning or reallocating the full struct. A final `finish()` returns an owned `T`. Achieving this unlocks ergonomic streaming deserialization while preserving jsonmodem’s low-allocation design, matching the example in `prompt.md` where intermediate prints expose partially initialized data.

## Progress

- [ ] (TBD) Complete Spike A (default-seeded snapshots) validating that seeding `TypedPartial<T>` with `T::default()` via `set_from_function` lets us lend `&T` between feeds without cloning.
- [ ] (TBD) Complete Spike B (event → outcome) validating JsonModem buffer events translate one-to-one into `facet_deserialize::Outcome` with accurate spans and scalar fidelity.
- [ ] (TBD) Implement the feature-gated adapter, options, errors, and tests across structs, enums, arrays, and failure cases.
- [ ] (TBD) Finalize documentation, examples, and rerun `.agent/check.sh` in both default and `facet` modes.

## Surprises & Discoveries

Use this section to log findings with explicit evidence paths.
- Pending entry (Spike A): document how the `set_from_function`-seeded pointer guard keeps borrows short-lived and safe while the parser mutates the same allocation.
- Pending entry (Spike B): capture any numeric normalization caveats (e.g., when to emit `Scalar::String` from `JsonModemBuffers`) with file references.

## Decision Log

Record design choices as they solidify.
- Decision: Use `JsonModemBuffers` as the ingestion layer so string fragments and structural offsets are already coalesced before translating to facet outcomes.
  Rationale: `JsonModemBuffers` mirrors `JsonModemValues`’ zero-copy guarantees and simplifies string handling.
  Status: Draft (2025-10-04).
- Decision: Implement an internal `FacetStateMachine` that drives `facet_reflect::Partial` directly from jsonmodem buffered events, avoiding `facet_deserialize::StackRunner`.
  Rationale: Keeps the adapter self-contained, eliminates private-API dependencies, and lets us tailor state management to streaming snapshots.
  Status: Draft (2025-10-05).
- Decision: Seed the root `TypedPartial<T>` with `T::default()` using `set_from_function`, retain the heap pointer, and gate borrows behind a short-lived guard between `feed()` calls.
  Rationale: Enables zero-clone snapshots while relying exclusively on public facet APIs and preserving jsonmodem’s streaming semantics.
  Status: Draft (2025-10-04).
- Decision: Gate all new code behind a `facet` feature that implicitly enables jsonmodem’s `std` support; leave the default build `no_std`.
  Rationale: the facet crates and our state machine rely on `std` by default, and gating avoids regressing existing embedded targets.
  Status: Draft (2025-10-04).

## Outcomes & Retrospective

Populate once spikes and implementation complete. Capture perf deltas (e.g., allocation counts vs `JsonModemValues`) and summarize any deviations from this ExecPlan.

## Context and Orientation

Repository layout summary for newcomers:
- Workspace root: `/Users/openai/demo-1/jsonmodem-1`.
- Primary crate: `crates/jsonmodem/`. Raw parser (`parser/`), event definitions (`event.rs`), and existing adapters (`jsonmodem_buffers.rs`, `jsonmodem_values.rs`).
- Reference material: clone `facet`, `facet-reflect`, `facet-json`, and `facet-deserialize` into `.agent/tmp/`. `facet-json/src/deserialize.rs` shows how JSON tokens map to `facet_deserialize::Outcome`. `facet-reflect/src/partial` documents `TypedPartial`, `HeapValue`, and `Peek` lifetimes.
- Tests: `crates/jsonmodem/tests/` hosts integration tests; add a `facet` submodule guarded by `cfg(feature = "facet")`.
- Tooling: `.agent/check.sh` orchestrates fmt, clippy, tests, and docs. Environment helpers like `JSONMODEM_TEST_FAST=1` speed up CI-equivalent runs.

## Plan of Work

Phase 0 – Tooling prep: confirm reference repos exist, or clone them. Annotate in this plan how to refresh them without polluting git.

Phase 1 – Spike: default-seeded borrow guard. Prototype `.agent/tmp/spikes/facet_seed_snapshot.rs` that seeds `TypedPartial<T>` with `T::default()` via `set_from_function`, captures the root pointer, and proves we can lend `&T` snapshots between JSON events without cloning or leaving the builder inconsistent. Document guard lifetimes and safety notes under `Surprises & Discoveries`.

Fallbacks if the spike fails:
- Fallback A: apply the unsafe layout shim that resets `Partial` tracker state after seeding `T::default()`, allowing pointer borrows without forking; document the safety invariants and guard lifetime.
- Fallback B: vendor `facet-reflect`/`facet-deserialize` and add an explicit `borrow_root` API so jsonmodem can obtain zero-copy snapshots with upstream-like semantics.

Phase 2 – Spike B (JsonModem outcome translation): build `.agent/tmp/spikes/jsonmodem_outcomes.rs` that feeds `JsonModemBuffers` with the prompt’s `json_chunks`. Translate `BufferedEvent` into `facet_deserialize::Outcome`/`Span` using candidate helper functions. Validate numbers and strings using assertions against `facet-json` by invoking `facet_json::from_str` for the same data. Record any divergence.

Phase 3 – Feature scaffolding: add optional dependencies to `crates/jsonmodem/Cargo.toml`, introduce `features = { std = ["dep:thiserror/std"], facet = ["std", "dep:facet", "dep:facet-reflect", "dep:facet-deserialize"] }`, enable `rust-version = "1.85"` default while documenting that `facet` raises the MSRV requirement to `1.87`. Update `crates/jsonmodem/src/lib.rs` to use `cfg(feature = "std")` for the global attribute and conditional module exports.

Phase 4 – Adapter implementation: create `crates/jsonmodem/src/jsonmodem_facet.rs` gated by `cfg(feature = "facet")`. Mirror `jsonmodem_values.rs` by layering `JsonModemBuffers` plus a `FacetStateMachine` that we own. Responsibilities:
- `FacetOptions` (public) toggling partial snapshot emission, buffer sizes, and span tracking.
- `JsonModemFacet<T, Ctx = backend::StdBackend>` storing parser/buffer state, a `FacetStateMachine<'facet, T>` plus `TypedPartial<'facet, T>` storage, a pointer-backed snapshot guard seeded with `T::default()`, and byte-offset tracking.
- `FacetStateMachine` translating `BufferedEvent` into low-level `Partial` operations without relying on `StackRunner`. Ensure numbers map to `Scalar::{U64,I64,F64,String}` exactly the way `facet-json` does; fall back to strings on overflow. Keep `Span` offsets consistent by incrementing with each fed chunk length. Document how the guard invalidates borrows before each mutation.
- Lending interface: `feed(&mut self, chunk: &str) -> Result<&T, JsonModemFacetError>` returns a borrow tied to the adapter lifetime, backed by the seeded pointer guard. Provide `view(&self) -> Option<&T>` for peeking without new chunks.
- `finish(self) -> Result<T, JsonModemFacetError>` flushes pending events, ensures the runner stack is empty, and materializes the owned object without extra clones.

Phase 5 – Testing and docs: craft unit and integration tests that cover struct streaming, nested `Vec`, enums, optional fields, invalid JSON, and facet reflection errors. Include the exact prompt scenario as an integration test verifying partial printouts evolve chunk-by-chunk. Add module docs and README updates explaining usage, feature gates, MSRV implications, and sample commands.

Phase 6 – Validation: run fmt, clippy, targeted tests, and `.agent/check.sh` with and without the `facet` feature to prove the adapter integrates cleanly.

## Concrete Steps

1. **Set up references (workspace root `/Users/openai/demo-1/jsonmodem-1`):**
       bash -lc "mkdir -p .agent/tmp && cd .agent/tmp && [ -d facet ] || git clone https://github.com/facet-rs/facet facet"
       bash -lc "cd .agent/tmp && [ -d facet-deserialize ] || git clone https://github.com/facet-rs/facet-deserialize"
       bash -lc "cd .agent/tmp && [ -d facet-json ] || git clone https://github.com/facet-rs/facet-json"
   Document commit SHAs in this plan once cloned.

2. **Spike – default-seeded snapshots (run from workspace root):**
       bash -lc "mkdir -p .agent/tmp/spikes && cargo new --bin .agent/tmp/spikes/facet_seed_snapshot"
       bash -lc "cd .agent/tmp/spikes/facet_seed_snapshot && cargo add facet-reflect@0.29 facet-deserialize@0.29"
       bash -lc "cd .agent/tmp/spikes/facet_seed_snapshot && cargo run"
   Verify `set_from_function` seeds `T::default()`, the root pointer remains valid across feeds, and snapshots drop before the next mutation. Log findings under `Surprises & Discoveries`.

3. **Spike B – JsonModem outcome translator:**
       bash -lc "cd .agent/tmp/spikes && cargo new --bin jsonmodem_outcomes"
       bash -lc "cd .agent/tmp/spikes/jsonmodem_outcomes && cargo add --path ../../crates/jsonmodem"
       bash -lc "cd .agent/tmp/spikes/jsonmodem_outcomes && cargo add facet-deserialize@0.29"
       bash -lc "cd .agent/tmp/spikes/jsonmodem_outcomes && cargo run"
   Confirm output matches `facet_json::from_str`. Record findings.

4. **Introduce feature plumbing (workspace root):**
       bash -lc "cd crates/jsonmodem && cargo add facet@0.29 --optional"
       bash -lc "cd crates/jsonmodem && cargo add facet-reflect@0.29 --optional --features alloc,std"
       bash -lc "cd crates/jsonmodem && cargo add facet-deserialize@0.29 --optional"
   Edit `Cargo.toml`, `src/lib.rs`, and update docs per Phase 3. Capture diffs.

5. **Implement `jsonmodem_facet.rs`:**
       bash -lc "${EDITOR:-nano} crates/jsonmodem/src/jsonmodem_facet.rs"
   Follow Phase 4 structure, reusing helpers from spikes. Keep internal comments explaining invariants for the pointer-backed snapshot guard.

6. **Add tests and examples:**
       bash -lc "mkdir -p crates/jsonmodem/tests/facet"
       bash -lc "${EDITOR:-nano} crates/jsonmodem/tests/facet/streaming.rs"
       bash -lc "${EDITOR:-nano} crates/jsonmodem/examples/facet_stream.rs"
   Include prompt scenario, nested cases, and failure assertions. Guard integration tests with `cfg(feature = "facet")`.

7. **Run validation commands (workspace root):**
       bash -lc "cargo fmt"
       bash -lc "cargo clippy --all-targets --all-features"
       bash -lc "cargo test -p jsonmodem --no-default-features"
       bash -lc "cargo test -p jsonmodem --features facet"
       bash -lc "JSONMODEM_TEST_FAST=1 JSONMODEM_BENCH_FAST=1 ./.agent/check.sh"
   Append command transcripts or summaries to `Artifacts & Notes`.

## Validation and Acceptance

The work is accepted when all of the following hold:
- Spike validates the default-seeded snapshot guard: `set_from_function` seeds `T::default()`, borrows stay short-lived, and guard drop semantics are documented in `Surprises & Discoveries`.
- Spike B proves `BufferedEvent` → `Outcome` translation accuracy, including numeric and string edge cases.
- `JsonModemFacet` streams the prompt’s `TestStruct` example with partial prints and yields the owned struct on `finish()`.
- Integration tests cover structs, enums, nested arrays, optional fields, malformed JSON, and facet reflection errors. All pass under `cargo test -p jsonmodem --features facet`.
- `.agent/check.sh` succeeds with default features and again with `--features facet` (or by enabling the feature via env/feature flags), confirming no regressions.
- Documentation (`README.md`, module docs) explains feature usage, MSRV implications, and includes runnable example commands.

## Idempotence and Recovery

All commands above are safe to rerun. Spikes live under `.agent/tmp/spikes` (gitignored) and can be rebuilt as needed. If `JsonModemFacet` enters an unrecoverable state during development, drop and recreate the adapter or call a documented `reset()` helper that clears the `FacetStateMachine` state. Document any non-idempotent behavior discovered during spikes so implementers can recover cleanly.

## Artifacts and Notes

Maintain concise evidence:
- Record spike outputs under `.agent/tmp/spikes/*/README.md` summarizing findings and integrate key conclusions here.
- Capture representative command transcripts (trimmed to essential lines) proving tests and examples run successfully. Include file paths and timestamps for traceability.
- If allocations are benchmarked, log before/after comparisons in this plan or a referenced artifact file.

## Interfaces and Dependencies

Public (feature gated):
- `pub struct JsonModemFacet<T, Ctx = backend::StdBackend>` with constructors `new()` and `with_options(JsonModemFacetOptions)`, plus `feed`, `finish`, `view`, and `reset` methods.
- `pub struct JsonModemFacetOptions` configuring parser/buffer/facet toggles.
- `pub enum JsonModemFacetError` covering parser, buffer assembler, facet reflection, numeric coercion, and state-machine violations.
- `pub type FacetResult<T> = Result<T, JsonModemFacetError>` and `pub struct FacetSnapshot<'a, T> { pub value: &'a T, pub bytes_consumed: usize, pub is_final: bool }`.

Internal helpers (stay behind `cfg(feature = "facet")`):
- `FacetStateMachine<T>` owning the `TypedPartial`, pointer-backed `SnapshotGuard`, and the event/navigation stack needed to mirror `facet` semantics.
- `OutcomeTranslator` mapping `BufferedEvent` + offsets into `facet_deserialize::Outcome` + `Span` using the same scalar logic as `facet-json`.
- `SpanTracker` accumulating byte counts per chunk.

Dependencies (all optional, feature = `facet`):
- `facet = { version = "0.29", optional = true, default-features = false, features = ["alloc", "std"] }`
- `facet-reflect = { version = "0.29", optional = true, default-features = false, features = ["alloc", "std"] }`
- `facet-deserialize = { version = "0.29", optional = true, default-features = false, features = ["alloc", "std"] }`
Ensure `Cargo.toml` comments explain MSRV implications and how to disable the feature for `no_std` consumers.
