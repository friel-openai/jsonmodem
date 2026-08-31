//! Compare cursor results and positions with the existing CPython/PyO3 APIs.

use std::panic::{AssertUnwindSafe, catch_unwind};

use pyo3::{
    ffi,
    prelude::*,
    types::{PyDict, iter::BoundDictIterator},
};

use super::{encoder, panic_text, run, write_owned};
use crate::compat::{
    Encoder, INDENT, NON_STR_KEYS,
    borrowed_dict::{DictScalarCursor, DictStep},
};

/// Preserve the distinction between a scalar write, an owned pair and an end.
#[derive(Debug, PartialEq)]
enum Step {
    Written,
    Owned,
    End,
    Panicked(String),
}

/// Independent C positions and PyO3 mutation checks for one scalar cursor.
struct CursorComparison<'py> {
    cursor: DictScalarCursor<'py>,
    owning: BoundDictIterator<'py>,
    // Obtained from a separate C call, not reconstructed from output count.
    c_position: ffi::Py_ssize_t,
    // Initial size, or -1 after the owning iterator reports a mutation.
    expected_size: ffi::Py_ssize_t,
    expected_remaining: ffi::Py_ssize_t,
    // Scalar cursor writes, with write_owned handling its owned results.
    actual: Encoder,
    // The existing owning iterator always uses write_owned.
    expected: Encoder,
    count: usize,
    expected_count: usize,
}

fn c_pair<'py>(
    dict: &Bound<'py, PyDict>,
    position: &mut ffi::Py_ssize_t,
) -> Option<(Bound<'py, PyAny>, Bound<'py, PyAny>)> {
    let mut key = std::ptr::null_mut();
    let mut value = std::ptr::null_mut();
    // SAFETY: dict is owned under the GIL, and all output variables are live.
    if unsafe { ffi::PyDict_Next(dict.as_ptr(), position, &mut key, &mut value) } == 0 {
        return None;
    }
    // SAFETY: a successful C call returns two entries retained by dict. Own
    // both before returning to test code that can allocate or run Python.
    Some(unsafe {
        (
            Bound::from_borrowed_ptr(dict.py(), key),
            Bound::from_borrowed_ptr(dict.py(), value),
        )
    })
}

impl<'py> CursorComparison<'py> {
    fn new(dict: Bound<'py, PyDict>, option: i32, padding: usize) -> Self {
        let size = dict.len() as ffi::Py_ssize_t;
        let mut actual = encoder::<false>();
        let mut expected = encoder::<false>();
        actual.option = option;
        expected.option = option;
        if padding != 0 {
            actual.output.resize(padding, b' ');
            expected.output.resize(padding, b' ');
        }
        Self {
            owning: dict.iter(),
            cursor: DictScalarCursor::new(dict),
            c_position: 0,
            expected_size: size,
            expected_remaining: size,
            actual,
            expected,
            count: 0,
            expected_count: 0,
        }
    }

    fn step(&mut self) -> PyResult<Step> {
        let start = self.actual.output.len();
        let count = self.count;
        let expected = catch_unwind(AssertUnwindSafe(|| self.owning.next()));
        if let Ok(pair) = &expected {
            let raw = c_pair(&self.cursor.dict, &mut self.c_position);
            match (pair, raw) {
                (Some((key, value)), Some((c_key, c_value))) => {
                    assert!(key.is(&c_key));
                    assert!(value.is(&c_value));
                    self.expected_remaining -= 1;
                }
                (None, None) => {}
                _ => panic!("C and PyO3 iteration disagree"),
            }
        }
        let actual = catch_unwind(AssertUnwindSafe(|| {
            self.cursor.next(&mut self.actual, &mut self.count, 1)
        }));
        let step = match expected {
            Ok(Some((key, value))) => {
                let step = match actual.expect("scalar cursor panicked before PyO3")? {
                    DictStep::Written => Step::Written,
                    DictStep::Owned(actual_key, actual_value) => {
                        assert!(actual_key.is(&key));
                        assert!(actual_value.is(&value));
                        assert_eq!(self.count, count);
                        assert_eq!(self.actual.output.len(), start);
                        write_owned(&mut self.actual, &mut self.count, actual_key, actual_value)?;
                        Step::Owned
                    }
                    DictStep::End => panic!("scalar cursor skipped an entry"),
                };
                write_owned(&mut self.expected, &mut self.expected_count, key, value)?;
                step
            }
            Ok(None) => {
                assert!(matches!(
                    actual.expect("scalar cursor panicked after PyO3 ended")?,
                    DictStep::End
                ));
                Step::End
            }
            Err(expected_panic) => {
                let Err(actual_panic) = actual else {
                    panic!("scalar cursor did not preserve PyO3's mutation panic");
                };
                let message = panic_text(expected_panic);
                assert_eq!(panic_text(actual_panic), message);
                self.expected_size = -1;
                Step::Panicked(message)
            }
        };
        assert_eq!(self.cursor.position, self.c_position);
        assert_eq!(self.cursor.original_size, self.expected_size);
        assert_eq!(self.cursor.remaining, self.expected_remaining);
        assert_eq!(self.count, self.expected_count);
        assert_eq!(self.actual.output[start..], self.expected.output[start..]);
        assert_eq!(self.actual.key_mask, self.expected.key_mask);
        assert!(self.actual.keys.iter().zip(&self.expected.keys).all(
            |((key, range), (expected_key, expected_range))| {
                key.as_ptr() == expected_key.as_ptr() && range == expected_range
            }
        ));
        assert_eq!(self.actual.keys.len(), self.expected.keys.len());
        Ok(step)
    }

    fn finish(&mut self) -> PyResult<()> {
        let limit = usize::try_from(self.expected_size).unwrap() + 2;
        for _ in 0..limit {
            match self.step()? {
                Step::Written | Step::Owned => {}
                Step::End => {
                    assert_eq!(self.step()?, Step::End);
                    return Ok(());
                }
                Step::Panicked(message) => panic!("unexpected mutation panic: {message}"),
            }
        }
        panic!("cursor did not reach the end");
    }
}

fn mapping<'py>(
    py: Python<'py>,
    source: &str,
) -> PyResult<(Bound<'py, PyDict>, Bound<'py, PyDict>)> {
    let namespace = PyDict::new(py);
    run(source, &namespace)?;
    let dict = namespace
        .get_item("mapping")?
        .unwrap()
        .downcast_into::<PyDict>()?;
    Ok((namespace, dict))
}

/// Inspect only PyO3's existing dictionary fields, never the private key table.
fn storage(dict: &Bound<'_, PyDict>) -> (usize, bool) {
    // SAFETY: this module is restricted to the full-API GIL configurations
    // that expose PyDictObject. The owned dictionary stays live under the GIL.
    // The saved address is compared only; it is not dereferenced after mutation.
    unsafe {
        let dict = dict.as_ptr().cast::<ffi::PyDictObject>();
        ((*dict).ma_keys.addr(), !(*dict).ma_values.is_null())
    }
}

#[test]
fn dense_dictionaries_match_c_api_at_table_growth_boundaries() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        for size in [0, 1, 5, 6, 85, 86, 21845, 21846] {
            let dict = PyDict::new(py);
            for index in 0..size {
                dict.set_item(format!("field_{index:05}"), index)?;
            }
            for (option, padding) in [(0, 0), (INDENT, 2048)] {
                let mut comparison = CursorComparison::new(dict.clone(), option, padding);
                comparison.finish()?;
                assert_eq!(comparison.c_position, size);
            }
        }
        Ok(())
    })
}

#[test]
fn deleted_entries_keep_c_api_positions_after_end() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        for (deleted, position) in [
            (vec!["a"], 3),
            (vec!["b"], 3),
            (vec!["c"], 2),
            (vec!["a", "b", "c"], 0),
        ] {
            let dict = PyDict::new(py);
            for (index, key) in ["a", "b", "c"].into_iter().enumerate() {
                dict.set_item(key, index)?;
            }
            for key in deleted {
                dict.del_item(key)?;
            }
            let mut comparison = CursorComparison::new(dict, 0, 0);
            comparison.finish()?;
            assert_eq!(comparison.c_position, position);
        }
        Ok(())
    })
}

#[test]
fn presized_general_table_with_string_keys_matches_c_api() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        // CPython's presized constructor selects general-key storage even
        // though every key inserted below is an exact string.
        // SAFETY: the GIL is held. The constructor returns a new reference
        // or null with a Python error; from_owned_ptr_or_err handles both.
        let dict =
            unsafe { Bound::<PyAny>::from_owned_ptr_or_err(py, ffi::_PyDict_NewPresized(100)) }?
                .downcast_into::<PyDict>()?;
        for index in 0..24 {
            dict.set_item(format!("field_{index:02}"), index)?;
        }
        assert!(!storage(&dict).1);
        let mut comparison = CursorComparison::new(dict, INDENT, 2048);
        comparison.finish()?;
        assert_eq!(comparison.c_position, 24);
        Ok(())
    })
}

#[test]
fn split_table_uses_each_instance_insertion_order() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let (_namespace, dict) = mapping(
            py,
            r#"
class Record:
    pass
first = Record()
first.a, first.b, first.c = 1, 2, 3
second = Record()
second.c, second.a = 30, 10
mapping = vars(second)
"#,
        )?;
        assert!(storage(&dict).1);
        let mut comparison = CursorComparison::new(dict, 0, 0);
        comparison.finish()?;
        assert_eq!(comparison.c_position, 2);
        assert_eq!(comparison.actual.output, b"{\"c\":30,\"a\":10");
        Ok(())
    })
}

#[test]
fn split_table_with_deleted_values_matches_c_api() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let (_namespace, dict) = mapping(
            py,
            r#"
class Record:
    pass
first = Record()
first.a, first.b, first.c = 1, 2, 3
second = Record()
second.c, second.a = 30, 10
del second.c
second.b = 20
mapping = vars(second)
"#,
        )?;
        assert!(storage(&dict).1);
        let mut comparison = CursorComparison::new(dict, INDENT, 0);
        comparison.finish()?;
        assert_eq!(comparison.c_position, 2);
        Ok(())
    })
}

#[test]
fn dense_table_resize_after_owned_entry_keeps_position() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let (namespace, dict) = mapping(
            py,
            "mapping = {'a': '\\u00e9', 'b': 2, 'c': 3, 'd': 4, 'e': 5}",
        )?;
        let before = storage(&dict).0;
        let mut comparison = CursorComparison::new(dict.clone(), 0, 2048);
        assert_eq!(comparison.step()?, Step::Owned);
        // The five-entry table has no unused insertion slots. Inserting f
        // after deleting a reallocates and compacts the table at equal length.
        run("del mapping['a']; mapping['f'] = 6", &namespace)?;
        assert_ne!(storage(&dict).0, before);
        comparison.finish()?;
        assert_eq!(comparison.c_position, 5);
        Ok(())
    })
}

#[test]
fn clear_and_refill_after_owned_entry_keeps_position() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let (namespace, dict) = mapping(py, "mapping = {'a': '\\u00e9', 'b': 2, 'c': 3}")?;
        let mut comparison = CursorComparison::new(dict, INDENT, 0);
        assert_eq!(comparison.step()?, Step::Owned);
        run(
            "mapping.clear(); mapping.update({'x': 10, 'y': 20, 'z': 30})",
            &namespace,
        )?;
        comparison.finish()?;
        assert_eq!(comparison.c_position, 3);
        Ok(())
    })
}

#[test]
fn unicode_to_general_after_owned_entry_keeps_position() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let (namespace, dict) = mapping(py, "mapping = {'a': '\\u00e9', 'b': 2, 'c': 3}")?;
        let before = storage(&dict).0;
        let mut comparison = CursorComparison::new(dict.clone(), NON_STR_KEYS, 2048);
        assert_eq!(comparison.step()?, Step::Owned);
        run("del mapping['b']; mapping[0] = 4", &namespace)?;
        assert_ne!(storage(&dict).0, before);
        comparison.finish()?;
        Ok(())
    })
}

#[test]
fn split_to_combined_after_owned_entry_keeps_position() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let (namespace, dict) = mapping(
            py,
            r#"
class Record:
    pass
owner = Record()
owner.a, owner.b, owner.c = '\u00e9', 2, 3
mapping = vars(owner)
"#,
        )?;
        assert!(storage(&dict).1);
        let mut comparison = CursorComparison::new(dict.clone(), NON_STR_KEYS | INDENT, 0);
        assert_eq!(comparison.step()?, Step::Owned);
        run("del mapping['b']; mapping[0] = 4", &namespace)?;
        assert!(!storage(&dict).1);
        comparison.finish()?;
        Ok(())
    })
}

#[test]
fn value_replacement_after_owned_entry_uses_current_entries() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let (namespace, dict) = mapping(py, "mapping = {'a': '\\u00e9', 'b': 2, 'c': 3}")?;
        let mut comparison = CursorComparison::new(dict, 0, 0);
        assert_eq!(comparison.step()?, Step::Owned);
        run(
            "mapping['b'] = 'replacement'; mapping['c'] = -(2**30)",
            &namespace,
        )?;
        assert_eq!(comparison.step()?, Step::Written);
        assert_eq!(comparison.step()?, Step::Owned);
        comparison.finish()?;
        Ok(())
    })
}

#[test]
fn end_does_not_fuse_iteration_or_stop_at_zero_remaining() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let (namespace, dict) = mapping(py, "mapping = {'a': 1, 'b': 2, 'c': 3}")?;
        let mut comparison = CursorComparison::new(dict, 0, 0);
        comparison.finish()?;
        assert_eq!(comparison.cursor.remaining, 0);
        run("del mapping['c']; mapping['d'] = 4", &namespace)?;
        assert_eq!(comparison.step()?, Step::Written);
        assert_eq!(comparison.cursor.remaining, -1);
        assert_eq!(
            comparison.step()?,
            Step::Panicked("dictionary keys changed during iteration".into())
        );
        assert_eq!(
            comparison.step()?,
            Step::Panicked("dictionary changed size during iteration".into())
        );
        Ok(())
    })
}

#[test]
fn size_change_after_end_keeps_the_sticky_panic() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let dict = PyDict::new(py);
        let mut comparison = CursorComparison::new(dict.clone(), 0, 0);
        comparison.finish()?;
        dict.set_item("a", 1)?;
        assert_eq!(
            comparison.step()?,
            Step::Panicked("dictionary changed size during iteration".into())
        );
        dict.clear();
        assert_eq!(
            comparison.step()?,
            Step::Panicked("dictionary changed size during iteration".into())
        );
        Ok(())
    })
}

#[test]
fn dictionary_subclass_does_not_call_python_iteration_methods() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let (_namespace, dict) = mapping(
            py,
            r#"
class Record(dict):
    def __iter__(self):
        raise AssertionError('__iter__')
    def items(self):
        raise AssertionError('items')
mapping = Record(a=1, b='text')
"#,
        )?;
        let mut comparison = CursorComparison::new(dict, 0, 0);
        comparison.finish()?;
        Ok(())
    })
}

#[test]
fn out_of_range_positions_end_without_obtaining_an_entry() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        for source in [
            "mapping = {}",
            "mapping = {'a': 1}",
            "mapping = {'a': 1, 'b': 2}; del mapping['b']",
        ] {
            let (_namespace, dict) = mapping(py, source)?;
            for position in [-1, ffi::Py_ssize_t::MAX] {
                let mut cursor = DictScalarCursor::new(dict.clone());
                cursor.position = position;
                let mut c_position = position;
                assert!(c_pair(&dict, &mut c_position).is_none());
                let mut output = encoder::<false>();
                let mut count = 0;
                assert!(matches!(
                    cursor.next(&mut output, &mut count, 1)?,
                    DictStep::End
                ));
                assert_eq!(cursor.position, c_position);
                assert_eq!(cursor.position, position);
                assert_eq!(cursor.remaining, dict.len() as ffi::Py_ssize_t);
                assert_eq!(count, 0);
                assert_eq!(output.output, b"{");
                assert!(output.keys.is_empty());
            }
        }
        Ok(())
    })
}
