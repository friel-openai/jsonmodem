//! Live-Python checks of owning fallbacks and dictionary mutation detection.

use std::{
    any::Any,
    ffi::CString,
    panic::{AssertUnwindSafe, catch_unwind},
};

use pyo3::{
    prelude::*,
    types::{PyDict, PyList, PyString, iter::BoundDictIterator},
};

use super::{DictScalarCursor, DictStep};
use crate::compat::{Encoder, INDENT, key_identity_bit};

/// The old owning iterator is a behavioral control in this test executable.
#[derive(Clone, Copy)]
enum CursorMode {
    Owning,
    Scalars,
}

enum TestCursor<'py> {
    Owning(BoundDictIterator<'py>),
    Scalars(DictScalarCursor<'py>),
}

#[test]
fn cursor_uses_the_same_storage_as_the_owning_iterator() {
    assert_eq!(
        std::mem::size_of::<DictScalarCursor<'static>>(),
        std::mem::size_of::<BoundDictIterator<'static>>(),
    );
}

impl<'py> TestCursor<'py> {
    fn new(dict: Bound<'py, PyDict>, mode: CursorMode) -> Self {
        match mode {
            CursorMode::Owning => Self::Owning(dict.iter()),
            CursorMode::Scalars => Self::Scalars(DictScalarCursor::new(dict)),
        }
    }

    fn step(&mut self, encoder: &mut Encoder, count: &mut usize) -> PyResult<DictStep<'py>> {
        match self {
            Self::Owning(iter) => Ok(match iter.next() {
                Some((key, value)) => DictStep::Owned(key, value),
                None => DictStep::End,
            }),
            Self::Scalars(iter) => iter.next(encoder, count, 1),
        }
    }
}

fn encoder<const CHECKED: bool>() -> Encoder<CHECKED> {
    Encoder {
        output: b"{".to_vec(),
        option: 0,
        base_depth: 0,
        dataclass_root: false,
        keys: Vec::new(),
        key_mask: 0,
        #[cfg(all(
            Py_3_12,
            not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
            not(any(py_sys_config = "Py_TRACE_REFS", py_sys_config = "Py_REF_DEBUG")),
            target_os = "linux",
            target_arch = "x86_64",
            target_pointer_width = "64",
            target_endian = "little",
        ))]
        integer_layout: crate::compat::IntegerLayout::Unchecked,
    }
}

fn run(source: &str, namespace: &Bound<'_, PyDict>) -> PyResult<()> {
    let source = CString::new(source).unwrap();
    // Functions defined here must use this same namespace as their globals.
    namespace
        .py()
        .run(&source, Some(namespace), Some(namespace))
}

fn refcounts(keys: &Bound<'_, PyList>) -> Vec<isize> {
    keys.iter().map(|key| key.get_refcnt()).collect()
}

fn write_owned(
    encoder: &mut Encoder,
    count: &mut usize,
    key: Bound<'_, PyAny>,
    value: Bound<'_, PyAny>,
) -> PyResult<()> {
    if *count != 0 {
        encoder.push(b',')?;
    }
    *count += 1;
    encoder.newline(1)?;
    assert!(encoder.key_any(&key)?);
    encoder.push(b':')?;
    if encoder.option & INDENT != 0 {
        encoder.push(b' ')?;
    }
    drop(key);
    assert!(encoder.scalar(&value)?);
    Ok(())
}

fn write_cursor(
    dict: Bound<'_, PyDict>,
    mode: CursorMode,
    encoder: &mut Encoder,
    count: &mut usize,
) -> PyResult<()> {
    let mut cursor = TestCursor::new(dict, mode);
    loop {
        match cursor.step(encoder, count)? {
            DictStep::Written => {}
            DictStep::Owned(key, value) => write_owned(encoder, count, key, value)?,
            DictStep::End => return Ok(()),
        }
    }
}

fn check_mixed_key_writers(first: CursorMode, second: CursorMode) -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let keys: Vec<_> = (0..24)
            .map(|index| PyString::new(py, &format!("fresh_cache_field_{index:02}")))
            .collect();
        let first_dict = PyDict::new(py);
        let second_dict = PyDict::new(py);
        let all = PyDict::new(py);
        for (index, key) in keys.iter().enumerate() {
            all.set_item(key, index)?;
            if index < 8 {
                first_dict.set_item(key, index)?;
            } else if index < 16 {
                second_dict.set_item(key, index)?;
            }
        }
        let mut encoder = encoder::<false>();
        encoder.output.resize(1024, b' ');
        let mut count = 0;
        write_cursor(first_dict, first, &mut encoder, &mut count)?;
        write_cursor(second_dict, second, &mut encoder, &mut count)?;
        assert_eq!(count, 16);
        let retained: Vec<_> = encoder.keys.iter().map(|(key, _)| key.as_ptr()).collect();
        assert_eq!(
            retained,
            keys[..16].iter().map(Bound::as_ptr).collect::<Vec<_>>()
        );
        let expected_mask = retained
            .iter()
            .fold(0, |mask, key| mask | key_identity_bit(*key as usize));
        assert_eq!(encoder.key_mask, expected_mask);
        let ranges: Vec<_> = encoder
            .keys
            .iter()
            .map(|(_, range)| range.clone())
            .collect();

        // Both writers must reuse admitted owners after the other writer filled
        // the cache, while new keys leave its owners and encoded ranges intact.
        let start = encoder.output.len();
        write_cursor(all.clone(), first, &mut encoder, &mut count)?;
        let first_output = encoder.output[start..].to_vec();
        let start = encoder.output.len();
        write_cursor(all, second, &mut encoder, &mut count)?;
        assert_eq!(encoder.output[start..], first_output);
        assert_eq!(count, 64);
        assert_eq!(encoder.key_mask, expected_mask);
        assert_eq!(
            encoder
                .keys
                .iter()
                .map(|(key, _)| key.as_ptr())
                .collect::<Vec<_>>(),
            retained,
        );
        assert_eq!(
            encoder
                .keys
                .iter()
                .map(|(_, range)| range.clone())
                .collect::<Vec<_>>(),
            ranges,
        );
        assert_eq!(encoder.into_checked().key_mask, expected_mask);
        Ok(())
    })
}

#[test]
fn borrowed_keys_are_visible_to_the_owning_writer() -> PyResult<()> {
    check_mixed_key_writers(CursorMode::Scalars, CursorMode::Owning)
}

#[test]
fn owning_keys_are_visible_to_the_borrowed_writer() -> PyResult<()> {
    check_mixed_key_writers(CursorMode::Owning, CursorMode::Scalars)
}

fn check_owned_fallback(mode: CursorMode) {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| -> PyResult<()> {
        for subclass_key in [true, false] {
            let namespace = PyDict::new(py);
            namespace.set_item("subclass_key", subclass_key)?;
            run(
                r#"
import gc
import weakref
events = []

class Key(str):
    def __del__(self):
        events.append("key")

class Value:
    def __del__(self):
        events.append("value")

keys = [f"fresh_field_{index:03d}".encode().decode() for index in range(32)]
mapping = {"padding": "x" * 2048}
mapping.update(dict.fromkeys(keys, 257))
key = Key("fallback") if subclass_key else b"fallback_exact".decode()
value = Value()
key_ref = weakref.ref(key) if subclass_key else None
value_ref = weakref.ref(value)
mapping[key] = value
del key, value
"#,
                &namespace,
            )?;
            let dict = namespace
                .get_item("mapping")?
                .unwrap()
                .downcast_into::<PyDict>()?;
            let keys = namespace
                .get_item("keys")?
                .unwrap()
                .downcast_into::<PyList>()?;
            let events = namespace
                .get_item("events")?
                .unwrap()
                .downcast_into::<PyList>()?;
            let key_ref = namespace.get_item("key_ref")?.unwrap();
            let value_ref = namespace.get_item("value_ref")?.unwrap();
            let before = refcounts(&keys);
            let mut cursor = TestCursor::new(dict.clone(), mode);
            let mut encoder = encoder::<false>();
            let mut count = 0;

            for _ in 0..33 {
                match cursor.step(&mut encoder, &mut count)? {
                    DictStep::Written => {}
                    DictStep::Owned(key, value) => {
                        write_owned(&mut encoder, &mut count, key, value)?
                    }
                    DictStep::End => panic!("missing scalar entry"),
                }
            }
            assert_eq!(count, 33);
            assert_eq!(encoder.keys.len(), 16);
            for (index, (owner, _)) in encoder.keys.iter().enumerate() {
                assert_eq!(owner.as_ptr(), keys.get_item(index)?.as_ptr());
            }
            let output = encoder.output.clone();
            let DictStep::Owned(key, value) = cursor.step(&mut encoder, &mut count)? else {
                panic!("fallback must return both owners");
            };
            assert_eq!(count, 33);
            assert_eq!(encoder.output, output);
            assert_eq!(encoder.keys.len(), 16);

            // Mutation and collection deliberately happen after step returns.
            // This checks ownership, not reentry within a borrowed operation.
            dict.clear();
            run("gc.collect()", &namespace)?;
            assert!(events.is_empty());
            assert_eq!(key.get_refcnt(), 1);
            assert_eq!(value.get_refcnt(), 1);
            assert!(value_ref.call0()?.is(&value));
            if subclass_key {
                assert!(key_ref.call0()?.is(&key));
            }
            assert_eq!(
                refcounts(&keys),
                before
                    .iter()
                    .enumerate()
                    .map(|(index, count)| { if index < 16 { *count } else { count - 1 } })
                    .collect::<Vec<_>>()
            );

            drop(key);
            if subclass_key {
                assert!(key_ref.call0()?.is_none());
                assert_eq!(events.extract::<Vec<String>>()?, ["key"]);
            } else {
                assert!(events.is_empty());
            }
            assert!(value_ref.call0()?.is(&value));
            drop(value);
            assert!(value_ref.call0()?.is_none());
            let expected = if subclass_key {
                vec!["key", "value"]
            } else {
                vec!["value"]
            };
            assert_eq!(events.extract::<Vec<String>>()?, expected);

            drop(encoder);
            assert_eq!(
                refcounts(&keys),
                before.iter().map(|count| count - 1).collect::<Vec<_>>()
            );
        }
        Ok(())
    })
    .unwrap();
}

#[test]
fn owning_iterator_keeps_fallback_pair_and_cached_keys_alive() {
    check_owned_fallback(CursorMode::Owning);
}

#[test]
fn scalar_cursor_keeps_fallback_pair_and_cached_keys_alive() {
    check_owned_fallback(CursorMode::Scalars);
}

fn panic_text(value: Box<dyn Any + Send>) -> String {
    if let Some(text) = value.downcast_ref::<&str>() {
        (*text).to_owned()
    } else if let Some(text) = value.downcast_ref::<String>() {
        text.clone()
    } else {
        panic!("unexpected panic payload");
    }
}

fn check_mutation(mode: CursorMode, same_size: bool) {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| -> PyResult<()> {
        let dict = PyDict::new(py);
        dict.set_item("a", 1)?;
        dict.set_item("b", 2)?;
        dict.set_item("c", 3)?;
        let mut cursor = TestCursor::new(dict.clone(), mode);
        let mut encoder = encoder::<false>();
        let mut count = 0;
        drop(cursor.step(&mut encoder, &mut count)?);
        if same_size {
            dict.del_item("a")?;
        }
        dict.set_item("d", 4)?;
        if same_size {
            // b, c and d remain after consuming a. The fourth total result
            // makes PyO3's remaining count -1 before its next mutation check.
            for _ in 0..3 {
                assert!(!matches!(
                    cursor.step(&mut encoder, &mut count)?,
                    DictStep::End
                ));
            }
        }
        let error = catch_unwind(AssertUnwindSafe(|| {
            cursor.step(&mut encoder, &mut count).unwrap();
        }))
        .expect_err("mutation was not detected");
        assert_eq!(
            panic_text(error),
            if same_size {
                "dictionary keys changed during iteration"
            } else {
                "dictionary changed size during iteration"
            }
        );
        let error = catch_unwind(AssertUnwindSafe(|| {
            cursor.step(&mut encoder, &mut count).unwrap();
        }))
        .expect_err("mutation failure was not sticky");
        assert_eq!(
            panic_text(error),
            "dictionary changed size during iteration"
        );
        Ok(())
    })
    .unwrap();
}

#[test]
fn owning_iterator_keeps_both_mutation_checks() {
    for same_size in [false, true] {
        check_mutation(CursorMode::Owning, same_size);
    }
}

#[test]
fn scalar_cursor_keeps_both_mutation_checks() {
    for same_size in [false, true] {
        check_mutation(CursorMode::Scalars, same_size);
    }
}

#[test]
fn rejected_entries_do_not_change_output_count_or_cache() {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| -> PyResult<()> {
        for source in [
            "key, value = 'ascii', '\\u00e9'",
            "key, value = '\\u00e9', 257",
            "key, value = 'ascii', int('1073741824')",
            "key, value = 'ascii', []",
            "key, value = 'ascii', {}",
            "key, value = 'ascii', ()",
            "key, value = 'ascii', object()",
            "key, value = 257, 'ascii'",
        ] {
            let namespace = PyDict::new(py);
            run(source, &namespace)?;
            let key = namespace.get_item("key")?.unwrap();
            let value = namespace.get_item("value")?.unwrap();
            let dict = PyDict::new(py);
            dict.set_item(&key, &value)?;
            let mut cursor = DictScalarCursor::new(dict);
            let mut encoder = encoder::<false>();
            encoder.output.resize(2048, b' ');
            let before = encoder.output.clone();
            let mut count = 0;
            let DictStep::Owned(returned_key, returned_value) =
                cursor.next(&mut encoder, &mut count, 1)?
            else {
                panic!("ineligible pair must be promoted");
            };
            assert!(returned_key.is(&key));
            assert!(returned_value.is(&value));
            assert_eq!(encoder.output, before);
            assert_eq!(count, 0);
            assert!(encoder.keys.is_empty());
        }
        Ok(())
    })
    .unwrap();
}

#[test]
fn checked_encoder_is_rejected_before_obtaining_an_entry() {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| -> PyResult<()> {
        let dict = PyDict::new(py);
        dict.set_item("a", 257)?;
        let mut cursor = DictScalarCursor::new(dict);
        let mut encoder = encoder::<true>();
        let mut count = 0;
        assert!(
            catch_unwind(AssertUnwindSafe(|| {
                cursor.next(&mut encoder, &mut count, 1).unwrap();
            }))
            .is_err()
        );
        assert_eq!(cursor.position, 0);
        assert_eq!(cursor.original_size, 1);
        assert_eq!(cursor.remaining, 1);
        assert_eq!(count, 0);
        assert_eq!(encoder.output, b"{");
        assert!(encoder.keys.is_empty());
        Ok(())
    })
    .unwrap();
}
