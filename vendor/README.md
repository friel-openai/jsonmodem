# PyO3 argument ownership and text conversion

`pyo3-0.25.1` contains source, tests, build files, documentation and licenses
from the public crates.io package with SHA-256
`8970a78afe0628a3e3430376fc5fd76b6b45c4d43360ffd6cdd40bdde72b682a`.
Release tooling, branding and unrelated project files are omitted.

Five files contain functional changes:

- `Cargo.toml` adds the `checked-unicode` marker feature. JSONModem requires
  this feature so a build cannot silently use the unpatched registry package.
- `src/types/string.rs` validates Python-produced bytes before making Rust
  strings. Its lossy error formatter reads canonical characters instead of
  invoking the replaceable `surrogatepass` codec handler. It handles C API
  failure and uses PyPy's exported name for `PyUnicode_ReadChar`.
- `src/pybacked.rs` checks the limited-API conversion before retaining a Rust
  string reference.
- `src/impl_/extract_argument.rs` owns keyword entries in Rust storage and
  borrows from that snapshot during tuple/dictionary argument extraction. It
  checks keyword types before conversion. The existing required-argument
  invariant is unchanged; its unsafe operation now has an explicit block.
- `src/types/dict.rs` removes the unused private borrowed-dictionary iterator.
  Generated argument parsing now uses owning entries instead.

The repository's pinned formatter also reorders one import list in
`src/pyclass/create_type_object.rs`. That change does not affect behavior.

`pyo3-macros-backend-0.25.1` comes from the public crate with SHA-256
`4109984c22491085343c05b0dbc54ddc405c3cf7b4374fc533f5c3313a572ccc`.
Only `src/params.rs` changes executable code. Generated tuple/dictionary wrappers retain the
snapshot through argument conversion, the Rust call and return conversion.
Fast function calls and direct `(*args, **kwargs)` forwarding are unchanged.
The matching runtime and macro patches must remain together.

Both package manifests exclude `Cargo.toml.orig` from repackaging because
Cargo reserves that filename for generated package metadata. The upstream
originals remain in this repository for comparison.

The added `rustfmt.toml` files keep the dependencies' 2021 formatting separate
from JSONModem's 2024 formatting.

Generated PyO3 argument parsing converts keyword names before JSONModem's
functions execute. It also formats Python exceptions during argument conversion.
Checks inside JSONModem alone cannot protect these operations. The patch applies
to every conversion, not just accelerated builds. It does not claim to audit
all of PyO3 or make the Python extension unsafe-free.

The workspace patch selects this copy for wheel and source-distribution builds.
The Python crate also declares local dependencies on the runtime and build-time
code generator so Maturin includes both in source archives. Workspace patches
alone are not enough for Maturin's path-dependency collection.
Keep the patch and required marker together. When upgrading PyO3, compare these
changes with the new release and run the invalid-cache and error-formatting
tests before removing the patch. Do not publish this copy as upstream PyO3.
