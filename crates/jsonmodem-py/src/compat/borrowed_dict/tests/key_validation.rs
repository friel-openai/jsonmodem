//! Primitive-key certification must not call Python or retain dictionary
//! entries.

use pyo3::{
    ffi,
    prelude::*,
    types::{PyDict, PyList},
};

use super::{encoder, run};
use crate::compat::borrowed_dict::primitive_keys_valid;

fn check(dict: &Bound<'_, PyDict>, expected: bool) {
    let entries: Vec<_> = dict.iter().collect();
    let counts: Vec<_> = entries
        .iter()
        .map(|(key, value)| (key.get_refcnt(), value.get_refcnt()))
        .collect();
    let dict_count = dict.get_refcnt();
    assert_eq!(primitive_keys_valid::<false>(dict), expected);
    assert!(!primitive_keys_valid::<true>(dict));
    assert_eq!(dict.get_refcnt(), dict_count);
    assert_eq!(
        entries
            .iter()
            .map(|(key, value)| (key.get_refcnt(), value.get_refcnt()))
            .collect::<Vec<_>>(),
        counts,
    );
    assert_eq!(
        dict.iter()
            .map(|(key, value)| (key.as_ptr(), value.as_ptr()))
            .collect::<Vec<_>>(),
        entries
            .iter()
            .map(|(key, value)| (key.as_ptr(), value.as_ptr()))
            .collect::<Vec<_>>(),
    );
}

fn check_source(source: &str, expected: bool) -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let namespace = PyDict::new(py);
        run("events = []", &namespace)?;
        run(source, &namespace)?;
        let dict = namespace
            .get_item("mapping")?
            .unwrap()
            .downcast_into::<PyDict>()?;
        check(&dict, expected);
        assert!(
            namespace
                .get_item("events")?
                .unwrap()
                .downcast::<PyList>()?
                .is_empty()
        );
        Ok(())
    })
}

#[test]
fn empty_and_exact_primitive_keys_are_certified() -> PyResult<()> {
    for source in [
        "mapping = {}",
        "mapping = {None: object()}",
        "mapping = {False: object(), True: object()}",
        "mapping = {0: object(), 1: object(), -1: object()}",
        "mapping = {2**30 - 1: object(), -(2**30) + 1: object()}",
        "mapping = {'': object(), 'a\\x00\\n\\\"\\\\z': object()}",
        "mapping = {0.0: object(), -1.25: object()}",
        "mapping = {-0.0: object()}",
        "mapping = {float('inf'): object(), float('-inf'): object(), float('nan'): object()}",
    ] {
        check_source(source, true)?;
    }
    Ok(())
}

#[test]
fn noncompact_integer_keys_restart_owning_validation() -> PyResult<()> {
    for source in [
        "mapping = {2**30: 0}",
        "mapping = {-(2**30): 0}",
        "mapping = {2**53: 0}",
        "mapping = {2**63 - 1: 0}",
        "mapping = {-(2**63): 0}",
        "mapping = {2**64 - 1: 0}",
        "mapping = {2**64: 0}",
        "mapping = {-(2**63) - 1: 0}",
    ] {
        check_source(source, false)?;
    }
    Ok(())
}

#[test]
fn late_uncertified_keys_leave_entries_unchanged() -> PyResult<()> {
    for key in [
        "2**30",
        "2**64",
        "'\\u00e9'",
        "'\\u0100'",
        "'\\U00010000'",
        "'\\ud800'",
        "type('Key', (str,), {})('subclass')",
        "type('Key', (int,), {})(2048)",
        "type('Key', (float,), {})(0.25)",
        "__import__('enum').Enum('Key', {'item': 2048}).item",
        "__import__('enum').IntEnum('Key', {'item': 2048}).item",
        "('unsupported',)",
    ] {
        check_source(
            &format!("mapping = dict.fromkeys(range(1024), None)\nmapping[{key}] = object()"),
            false,
        )?;
    }
    Ok(())
}

#[test]
fn deleted_combined_dictionary_entries_are_skipped() -> PyResult<()> {
    check_source(
        r#"
mapping = dict.fromkeys(range(1024), None)
mapping[2**64] = object()
mapping['\ud800'] = object()
del mapping[2**64], mapping['\ud800']
for key in range(0, 1024, 3):
    del mapping[key]
mapping[-1] = object()
"#,
        true,
    )
}

#[test]
fn split_dictionary_uses_live_values_and_instance_order() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let namespace = PyDict::new(py);
        run(
            r#"
class Record:
    pass
first = Record()
first.a, first.b, first.c = 1, 2, 3
second = Record()
second.c, second.a = 30, 10
del second.c
second.b = object()
mapping = vars(second)
"#,
            &namespace,
        )?;
        let dict = namespace
            .get_item("mapping")?
            .unwrap()
            .downcast_into::<PyDict>()?;
        // SAFETY: the selected full-API CPython layout exposes PyDictObject.
        // dict retains this object under the GIL throughout the field read.
        assert!(unsafe {
            !(*dict.as_ptr().cast::<ffi::PyDictObject>())
                .ma_values
                .is_null()
        });
        check(&dict, true);
        dict.set_item("\u{e9}", 1)?;
        check(&dict, false);
        Ok(())
    })
}

#[test]
fn validation_does_not_call_key_or_value_methods() -> PyResult<()> {
    check_source(
        r#"
class Value:
    def __getattribute__(self, name):
        events.append(('get', name))
        raise AssertionError(name)
    def __del__(self):
        events.append('del')

class Key(str):
    def __str__(self):
        events.append('str')
        raise AssertionError('__str__')
    def __len__(self):
        events.append('len')
        raise AssertionError('__len__')

mapping = {index: Value() for index in range(1024)}
mapping[Key('last')] = Value()
"#,
        false,
    )
}

#[test]
fn checked_prevalidation_keeps_owning_conversions_without_output() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let namespace = PyDict::new(py);
        run(
            "mapping = dict.fromkeys(range(1024), None)\nmapping[2**64 - 1] = 0\nmapping['\\u00e9'] = 0",
            &namespace,
        )?;
        let dict = namespace
            .get_item("mapping")?
            .unwrap()
            .downcast_into::<PyDict>()?;
        let mut checked = encoder::<true>();
        let mut ordinary = encoder::<false>();
        assert!(!primitive_keys_valid::<true>(&dict));
        assert!(checked.validate_keys(&dict)?);
        assert!(ordinary.validate_keys(&dict)?);
        assert_eq!(checked.output, b"{");
        assert_eq!(ordinary.output, b"{");
        Ok(())
    })
}
