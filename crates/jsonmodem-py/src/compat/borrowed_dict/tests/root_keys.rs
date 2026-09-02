//! Root helper checks must exclude equality callbacks without reading entries.

use pyo3::{
    prelude::*,
    types::{PyDict, PyList},
};

use super::super::has_exact_unicode_keys;

fn fixture(py: Python<'_>) -> PyResult<Bound<'_, PyDict>> {
    let namespace = PyDict::new(py);
    py.run(
        pyo3::ffi::c_str!(
            r#"
calls = []

class Key:
    def __hash__(self):
        return hash("target")
    def __eq__(self, other):
        calls.append("object")
        return other == "target"

class StrKey(str):
    __hash__ = str.__hash__
    def __eq__(self, other):
        calls.append("str")
        return str.__eq__(self, other)

class DictSubclass(dict):
    def __getitem__(self, key):
        raise AssertionError("dictionary methods must not run")

class Owner:
    pass

owner = Owner()
owner.target = 7
empty = {}
unicode_keys = {"target": 7}
holes = {str(index): index for index in range(40)}
del holes["17"]
split = owner.__dict__
object_key = {Key(): 7}
str_key = {StrKey("target"): 7}
converted = {"target": 7, 0: 0}
del converted[0]
subclass = DictSubclass(target=7)
calls.clear()
"#
        ),
        Some(&namespace),
        Some(&namespace),
    )?;
    Ok(namespace)
}

#[test]
fn root_key_check_accepts_unicode_tables_with_holes_and_split_storage() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let namespace = fixture(py)?;
        for name in ["empty", "unicode_keys", "holes", "split"] {
            let dict = namespace
                .get_item(name)?
                .unwrap()
                .downcast_into::<PyDict>()?;
            assert!(has_exact_unicode_keys(&dict), "{name}");
        }
        Ok(())
    })
}

#[test]
fn root_key_check_rejects_custom_keys_without_equality() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let namespace = fixture(py)?;
        let calls = namespace
            .get_item("calls")?
            .unwrap()
            .downcast_into::<PyList>()?;
        for name in ["object_key", "str_key", "converted", "subclass"] {
            let dict = namespace
                .get_item(name)?
                .unwrap()
                .downcast_into::<PyDict>()?;
            assert!(!has_exact_unicode_keys(&dict), "{name}");
        }
        assert!(calls.is_empty());
        for name in ["object_key", "str_key"] {
            let dict = namespace
                .get_item(name)?
                .unwrap()
                .downcast_into::<PyDict>()?;
            assert!(dict.get_item("target")?.is_some());
        }
        assert_eq!(calls.len(), 2);
        Ok(())
    })
}

#[test]
fn root_key_check_reads_the_current_table_after_mutation() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let dict = PyDict::new(py);
        dict.set_item("target", 7)?;
        assert!(has_exact_unicode_keys(&dict));
        dict.set_item(0, 9)?;
        assert!(!has_exact_unicode_keys(&dict));
        dict.del_item(0)?;
        assert!(!has_exact_unicode_keys(&dict));
        dict.clear();
        dict.set_item("target", 11)?;
        assert!(has_exact_unicode_keys(&dict));
        Ok(())
    })
}
