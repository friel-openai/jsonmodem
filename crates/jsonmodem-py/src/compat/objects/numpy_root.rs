//! Exact root numeric containers finish in Rust storage before Python
//! allocation.

use pyo3::{
    prelude::*,
    types::{PyBytes, PyCFunction, PyDict, PyFunction, PyList, PyModule, PyString, PyTuple},
};

use super::{
    super::{
        Encoder, IntegerLayout, OutputAllocationError, borrowed_dict::has_exact_unicode_keys,
        output::OutputBuffer,
    },
    APPEND_NEWLINE, INITIAL_OUTPUT_CAPACITY, SERIALIZE_NUMPY, allocation_error,
};
use crate::{
    numpy::{NumericScalarTypes, ScalarValue},
    text::compact_ascii_text,
};

#[inline]
pub(super) fn try_dumps(
    obj: &Bound<'_, PyAny>,
    option: i32,
    helpers: &Bound<'_, PyAny>,
) -> PyResult<Option<Py<PyBytes>>> {
    if option & SERIALIZE_NUMPY == 0 || option & !(SERIALIZE_NUMPY | APPEND_NEWLINE) != 0 {
        return Ok(None);
    }
    if obj.is_exact_instance_of::<PyList>() || obj.is_exact_instance_of::<PyTuple>() {
        write_root(obj, option, helpers.downcast::<PyTuple>()?)
    } else if let Ok(dict) = obj.downcast_exact::<PyDict>() {
        write_dict(dict, option, helpers.downcast::<PyTuple>()?)
    } else {
        Ok(None)
    }
}

/// The attempt may decline only before any Python callback or publication.
#[inline(never)]
fn write_root(
    obj: &Bound<'_, PyAny>,
    option: i32,
    helpers: &Bound<'_, PyTuple>,
) -> PyResult<Option<Py<PyBytes>>> {
    if helpers.len() <= 13 {
        return Ok(None);
    }
    let table = helpers.get_borrowed_item(12)?;
    let defaults = helpers.get_borrowed_item(13)?;
    let (Ok(table), Ok(defaults)) = (
        table.downcast::<NumericScalarTypes>(),
        defaults.downcast::<PyTuple>(),
    ) else {
        return Ok(None);
    };
    let types = table.get();
    let Some(queries) = types.root_query_names() else {
        return Ok(None);
    };
    // value() gives an aliased Enum helper priority over a nonempty container.
    let enum_type = helpers.get_borrowed_item(0)?;
    if obj
        .get_type()
        .mro()
        .iter_borrowed()
        .any(|base| base.is(enum_type))
    {
        return Ok(None);
    }
    let snapshot = if let Ok(list) = obj.downcast_exact::<PyList>() {
        types.root_snapshot(list.iter())
    } else {
        types.root_snapshot(obj.downcast_exact::<PyTuple>()?.iter())
    }
    .map_err(|_| allocation_error())?;
    let Some(snapshot) = snapshot else {
        return Ok(None);
    };
    if snapshot.is_empty() || !helpers_are_default(defaults, &helpers.get_item(3)?, queries)? {
        return Ok(None);
    }

    // From snapshot admission through the last write, real NumPy numeric
    // PyBUF_SIMPLE slots neither allocate Python objects nor call Python or
    // release the GIL. Snapshot/type/helper owners keep decrements nonfinal.
    // Only Rust allocation is allowed here; do not substitute PythonOutput.
    let mut output = Vec::new();
    OutputBuffer::reserve::<true>(&mut output, INITIAL_OUTPUT_CAPACITY)?;
    OutputBuffer::push::<true>(&mut output, b'[')?;
    for (index, scalar) in snapshot.iter().enumerate() {
        let Some(number) = scalar.copy()? else {
            return Ok(None);
        };
        if index != 0 {
            OutputBuffer::push::<true>(&mut output, b',')?;
        }
        write_number(&mut output, number)?;
    }
    OutputBuffer::push::<true>(&mut output, b']')?;
    if option & APPEND_NEWLINE != 0 {
        OutputBuffer::push::<true>(&mut output, b'\n')?;
    }
    // Python allocation starts only now. Success or error ends the attempt;
    // neither may resume serialization using the earlier helper checks.
    output.finish(obj.py()).map(Some)
}

/// ASCII keys and exact numeric values can finish without Python conversion.
#[inline(never)]
fn write_dict(
    dict: &Bound<'_, PyDict>,
    option: i32,
    helpers: &Bound<'_, PyTuple>,
) -> PyResult<Option<Py<PyBytes>>> {
    if helpers.len() <= 13 {
        return Ok(None);
    }
    let table = helpers.get_borrowed_item(12)?;
    let defaults = helpers.get_borrowed_item(13)?;
    let (Ok(table), Ok(defaults)) = (
        table.downcast::<NumericScalarTypes>(),
        defaults.downcast::<PyTuple>(),
    ) else {
        return Ok(None);
    };
    let types = table.get();
    let Some(queries) = types.root_query_names() else {
        return Ok(None);
    };
    let enum_type = helpers.get_borrowed_item(0)?;
    if dict
        .get_type()
        .mro()
        .iter_borrowed()
        .any(|base| base.is(enum_type))
    {
        return Ok(None);
    }
    let Some(snapshot) = types
        .root_dict_snapshot(dict.iter())
        .map_err(|_| allocation_error())?
    else {
        return Ok(None);
    };
    if snapshot.is_empty() || !helpers_are_default(defaults, &helpers.get_item(3)?, queries)? {
        return Ok(None);
    }

    // Only Rust allocation is allowed before publication, as in write_root.
    // Encoder::string reuses JSON escaping but must receive an existing view:
    // converting a surrogate key could call a replaced strict codec handler.
    let mut encoder = Encoder::<true> {
        output: Vec::new(),
        option,
        base_depth: 0,
        dataclass_root: false,
        integer_layout: IntegerLayout::Unchecked,
        keys: Vec::new(),
        key_mask: 0,
    };
    encoder.reserve(INITIAL_OUTPUT_CAPACITY)?;
    encoder.push(b'{')?;
    for (index, field) in snapshot.iter().enumerate() {
        let Some(key) = compact_ascii_text(&field.key) else {
            return Ok(None);
        };
        if index != 0 {
            encoder.push(b',')?;
        }
        encoder.string(key)?;
        encoder.push(b':')?;
        let Some(number) = field.value.copy()? else {
            return Ok(None);
        };
        write_number(&mut encoder.output, number)?;
    }
    encoder.push(b'}')?;
    if option & APPEND_NEWLINE != 0 {
        encoder.push(b'\n')?;
    }
    // No decline may follow this first Python allocation, even on failure.
    encoder.bytes(dict.py()).map(Some)
}

#[inline]
fn write_number(output: &mut Vec<u8>, number: ScalarValue) -> Result<(), OutputAllocationError> {
    match number {
        ScalarValue::Bool(value) => {
            OutputBuffer::extend::<true>(output, if value { b"true" } else { b"false" })
        }
        ScalarValue::Signed(value) => {
            OutputBuffer::extend::<true>(output, itoa::Buffer::new().format(value).as_bytes())
        }
        ScalarValue::Unsigned(value) => {
            OutputBuffer::extend::<true>(output, itoa::Buffer::new().format(value).as_bytes())
        }
        ScalarValue::Float32(value) => {
            let mut buffer = zmij::Buffer::new();
            OutputBuffer::extend::<true>(
                output,
                if value.is_finite() {
                    buffer.format_finite(value).as_bytes()
                } else {
                    b"null"
                },
            )
        }
        ScalarValue::Float64(value) => {
            let mut buffer = zmij::Buffer::new();
            OutputBuffer::extend::<true>(
                output,
                if value.is_finite() {
                    buffer.format_finite(value).as_bytes()
                } else {
                    b"null"
                },
            )
        }
    }
}

/// All three current key tables must exclude user-defined equality first.
fn helpers_are_default(
    helpers: &Bound<'_, PyTuple>,
    special: &Bound<'_, PyAny>,
    queries: &[Py<PyString>; 6],
) -> PyResult<bool> {
    if helpers.len() != 8 {
        return Ok(false);
    }
    let py = helpers.py();
    let modules = helpers.get_borrowed_item(0)?;
    let module = helpers.get_borrowed_item(1)?;
    let native = helpers.get_borrowed_item(2)?;
    let numpy = helpers.get_borrowed_item(3)?;
    let encode = helpers.get_borrowed_item(4)?;
    let default_special = helpers.get_borrowed_item(5)?;
    let native_dumps = helpers.get_borrowed_item(6)?;
    let scalar_types = helpers.get_borrowed_item(7)?;
    if !special.is(default_special)
        || !modules.is_exact_instance_of::<PyDict>()
        || !module.is_exact_instance_of::<PyModule>()
        || !native.is_exact_instance_of::<PyModule>()
        || !numpy.is_exact_instance_of::<PyModule>()
        || !native_dumps.is_exact_instance_of::<PyCFunction>()
        || !scalar_types.is_exact_instance_of::<PyTuple>()
        || !encode.is_exact_instance_of::<PyFunction>()
        || !default_special.is_exact_instance_of::<PyFunction>()
    {
        return Ok(false);
    }
    let modules = modules.downcast::<PyDict>()?;
    let module_dict = module.downcast::<PyModule>()?.dict();
    let native_dict = native.downcast::<PyModule>()?.dict();
    if !has_exact_unicode_keys(modules)
        || !has_exact_unicode_keys(&module_dict)
        || !has_exact_unicode_keys(&native_dict)
    {
        return Ok(false);
    }
    let [
        module_name,
        encode_name,
        native_name,
        dumps_name,
        types_name,
        numpy_name,
    ] = queries;
    Ok(modules
        .get_item(module_name.bind(py))?
        .is_some_and(|current| current.is(module))
        && module_dict
            .get_item(encode_name.bind(py))?
            .is_some_and(|current| current.is(encode))
        && module_dict
            .get_item(native_name.bind(py))?
            .is_some_and(|current| current.is(native))
        && native_dict
            .get_item(dumps_name.bind(py))?
            .is_some_and(|current| current.is(native_dumps))
        && module_dict
            .get_item(types_name.bind(py))?
            .is_some_and(|current| current.is(scalar_types))
        && module_dict
            .get_item(numpy_name.bind(py))?
            .is_some_and(|current| current.is(numpy)))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn compact_ascii_keys_decline_without_conversion() -> PyResult<()> {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            for text in ["", "plain", "quote\"slash\\nul\0control\x1f"] {
                let key = PyString::new(py, text);
                assert_eq!(compact_ascii_text(&key), Some(text));
            }
            let fixture = PyModule::from_code(
                py,
                pyo3::ffi::c_str!(
                    r#"
class Key(str):
    pass
keys = (Key("plain"), chr(0xe9) * 17, chr(0x100), chr(0x1f600), chr(0xd800))
"#
                ),
                pyo3::ffi::c_str!("numpy_dict_key_fixture.py"),
                pyo3::ffi::c_str!("numpy_dict_key_fixture"),
            )?;
            let keys = fixture.getattr("keys")?.downcast_into::<PyTuple>()?;
            for key in keys.iter() {
                assert!(compact_ascii_text(key.downcast::<PyString>()?).is_none());
                assert!(!PyErr::occurred(py));
            }
            Ok(())
        })
    }

    #[test]
    #[ignore = "requires NumPy and the matching jsonmodem Python helpers"]
    fn exact_numeric_roots_use_the_vec_writer() -> PyResult<()> {
        check_numeric_roots(false)
    }

    #[test]
    #[ignore = "requires NumPy, orjson, and the matching jsonmodem Python helpers"]
    fn exact_numeric_dicts_use_the_vec_writer() -> PyResult<()> {
        check_numeric_roots(true)
    }

    fn check_numeric_roots(dictionaries: bool) -> PyResult<()> {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let fixture = PyModule::from_code(
                py,
                pyo3::ffi::c_str!(
                    r#"
import sys
from unittest.mock import patch

import numpy as np
from jsonmodem import _compat, _numpy

def prepare(native, dictionaries):
    scalar_types = _numpy.SCALAR_TYPES
    table = native._NumericScalarTypes(np, scalar_types)
    special = _compat._ENCODER_HELPERS[3]
    defaults = (
        sys.modules, _numpy, native, np, _numpy.encode,
        special, native._numpy_dumps, scalar_types,
    )
    values = [np.int64(7)] * 1024
    roots = [(values, b"[" + b",".join([b"7"] * 1024) + b"]")]
    roots.append((tuple(values), roots[0][1]))
    if dictionaries:
        import orjson
        roots = []
        for dtype in (
            np.bool_, np.int8, np.int16, np.int32, np.int64,
            np.uint8, np.uint16, np.uint32, np.uint64,
            np.float16, np.float32, np.float64,
        ):
            value = {f"key_{index:03}": dtype(7) for index in range(128)}
            value['quote"slash\\control\x00'] = dtype(1)
            roots.append((value, orjson.dumps(value, option=16)))
    return {
        "module": _numpy,
        "original_native": _numpy.native,
        "context": patch.object(_numpy, "native", native),
        "helpers": _compat._ENCODER_HELPERS[:12] + (table, defaults),
        "roots": tuple(roots),
    }
"#
                ),
                pyo3::ffi::c_str!("numpy_root_admission_fixture.py"),
                pyo3::ffi::c_str!("numpy_root_admission_fixture"),
            )?;
            // A second extension's PyO3 class would not prove this binary's
            // admission. Bind the fixture to the class and function tested here.
            let native = PyModule::new(py, "_numpy_root_admission_test_native")?;
            native.add_function(pyo3::wrap_pyfunction!(crate::numpy::_numpy_dumps, &native)?)?;
            native.add_class::<NumericScalarTypes>()?;
            let setup = fixture.getattr("prepare")?.call1((&native, dictionaries))?;
            let module = setup.get_item("module")?;
            let original_native = setup.get_item("original_native")?;
            let context = setup.get_item("context")?;
            context.call_method0("__enter__")?;
            let outcome =
                std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> PyResult<()> {
                    let helpers = setup.get_item("helpers")?.downcast_into::<PyTuple>()?;
                    let roots = setup.get_item("roots")?.downcast_into::<PyTuple>()?;
                    for case in roots.iter() {
                        let root = case.get_item(0)?;
                        let expected = case.get_item(1)?.downcast_into::<PyBytes>()?;
                        let bytes = try_dumps(&root, 16, helpers.as_any())?
                            .expect("the exact numeric root must use the Vec writer");
                        assert_eq!(bytes.bind(py).as_bytes(), expected.as_bytes());
                        let bytes = try_dumps(&root, 16 | APPEND_NEWLINE, helpers.as_any())?
                            .expect("newline output must remain admitted");
                        assert_eq!(bytes.bind(py).as_bytes().last(), Some(&b'\n'));
                        assert_eq!(
                            &bytes.bind(py).as_bytes()[..bytes.bind(py).as_bytes().len() - 1],
                            expected.as_bytes()
                        );
                    }
                    Ok(())
                }));
            context.call_method1("__exit__", (py.None(), py.None(), py.None()))?;
            assert!(module.getattr("native")?.is(&original_native));
            match outcome {
                Ok(result) => result,
                Err(panic) => std::panic::resume_unwind(panic),
            }
        })
    }
}
