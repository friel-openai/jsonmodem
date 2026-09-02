//! Exercise Python result constructors with one real object-allocation failure.

#![cfg(all(
    not(any(
        py_sys_config = "Py_DEBUG",
        py_sys_config = "Py_REF_DEBUG",
        py_sys_config = "Py_TRACE_REFS",
    )),
    target_os = "linux",
    target_arch = "x86_64",
    target_pointer_width = "64",
    target_endian = "little",
))]

use std::{
    ffi::c_void,
    mem::{MaybeUninit, size_of},
    sync::{
        Arc,
        atomic::{AtomicBool, AtomicUsize, Ordering},
    },
};

use pyo3::{
    exceptions::{PyMemoryError, PyRuntimeError},
    ffi,
    prelude::*,
    types::{PyBytes, PyBytesMethods, PyCFunction, PyModule, PyString},
};

type Malloc = extern "C" fn(*mut c_void, usize) -> *mut c_void;
type Calloc = extern "C" fn(*mut c_void, usize, usize) -> *mut c_void;
type Realloc = extern "C" fn(*mut c_void, *mut c_void, usize) -> *mut c_void;
type Free = extern "C" fn(*mut c_void, *mut c_void);

/// Delegate to the saved allocator except for one exact object allocation.
struct HookState {
    previous: ffi::PyMemAllocatorEx,
    malloc: Malloc,
    calloc: Calloc,
    realloc: Realloc,
    free: Free,
    requested_bytes: usize,
    armed: AtomicBool,
    matched_calls: AtomicUsize,
    failed_calls: AtomicUsize,
    observed_bytes: AtomicUsize,
    // Observe one parent allocation until collection frees its storage.
    parent_bytes: usize,
    parent_address: AtomicUsize,
    parent_freed: AtomicBool,
}

extern "C" fn hooked_malloc(context: *mut c_void, size: usize) -> *mut c_void {
    // SAFETY: The guard keeps this immutable context live until restoration.
    let hook = unsafe { &*context.cast::<HookState>() };
    if size == hook.requested_bytes {
        hook.matched_calls.fetch_add(1, Ordering::Relaxed);
        hook.observed_bytes.store(size, Ordering::Relaxed);
        if hook.armed.swap(false, Ordering::Relaxed) {
            hook.failed_calls.fetch_add(1, Ordering::Relaxed);
            return std::ptr::null_mut();
        }
    }
    let pointer = (hook.malloc)(hook.previous.ctx, size);
    if hook.parent_bytes != 0 && size == hook.parent_bytes && !pointer.is_null() {
        let _ = hook.parent_address.compare_exchange(
            0,
            pointer.addr(),
            Ordering::Relaxed,
            Ordering::Relaxed,
        );
    }
    pointer
}

extern "C" fn hooked_calloc(context: *mut c_void, count: usize, size: usize) -> *mut c_void {
    // SAFETY: The guard keeps this immutable context live until restoration.
    let hook = unsafe { &*context.cast::<HookState>() };
    (hook.calloc)(hook.previous.ctx, count, size)
}

extern "C" fn hooked_realloc(
    context: *mut c_void,
    pointer: *mut c_void,
    size: usize,
) -> *mut c_void {
    // SAFETY: The guard keeps this immutable context live until restoration.
    let hook = unsafe { &*context.cast::<HookState>() };
    (hook.realloc)(hook.previous.ctx, pointer, size)
}

extern "C" fn hooked_free(context: *mut c_void, pointer: *mut c_void) {
    // SAFETY: The guard keeps this immutable context live until restoration.
    let hook = unsafe { &*context.cast::<HookState>() };
    if !pointer.is_null() && pointer.addr() == hook.parent_address.load(Ordering::Relaxed) {
        hook.parent_freed.store(true, Ordering::Relaxed);
    }
    (hook.free)(hook.previous.ctx, pointer);
}

fn allocator() -> ffi::PyMemAllocatorEx {
    let mut saved = MaybeUninit::uninit();
    // SAFETY: All callers hold the GIL in a serial native test process. The
    // output is writable storage for the complete allocator record.
    unsafe {
        ffi::PyMem_GetAllocator(
            ffi::PyMemAllocatorDomain::PYMEM_DOMAIN_OBJ,
            saved.as_mut_ptr(),
        );
        saved.assume_init()
    }
}

fn allocator_identity(value: ffi::PyMemAllocatorEx) -> [usize; 5] {
    [
        value.ctx.addr(),
        value.malloc.map_or(0, |callback| callback as usize),
        value.calloc.map_or(0, |callback| callback as usize),
        value.realloc.map_or(0, |callback| callback as usize),
        value.free.map_or(0, |callback| callback as usize),
    ]
}

/// Restore the allocator before releasing its context, including on unwind.
struct FailObjectAllocation<'py> {
    state: Box<HookState>,
    _py: Python<'py>,
}

/// Copy observations before restoration; assertions run only afterward.
struct FailureReceipt {
    requested_bytes: usize,
    matched_calls: usize,
    failed_calls: usize,
    observed_bytes: usize,
    saved_allocator: [usize; 5],
    parent_address: usize,
    parent_freed: bool,
}

impl<'py> FailObjectAllocation<'py> {
    fn unicode(py: Python<'py>, document: &str) -> Self {
        assert!(document.len() >= 1024 && document.is_ascii());
        let requested_bytes = size_of::<ffi::PyASCIIObject>()
            .checked_add(document.len())
            .and_then(|size| size.checked_add(1))
            .expect("ASCII object allocation fits usize");
        Self::install(py, requested_bytes)
    }

    fn bytes(py: Python<'py>, length: usize) -> Self {
        let requested_bytes = std::mem::offset_of!(ffi::PyBytesObject, ob_sval)
            .checked_add(length)
            .and_then(|size| size.checked_add(1))
            .expect("bytes object allocation fits usize");
        Self::install(py, requested_bytes)
    }

    fn install(py: Python<'py>, requested_bytes: usize) -> Self {
        Self::install_with_parent(py, requested_bytes, 0)
    }

    fn install_with_parent(py: Python<'py>, requested_bytes: usize, parent_bytes: usize) -> Self {
        let previous = allocator();
        let mut guard = Self {
            state: Box::new(HookState {
                previous,
                malloc: previous.malloc.expect("installed malloc"),
                calloc: previous.calloc.expect("installed calloc"),
                realloc: previous.realloc.expect("installed realloc"),
                free: previous.free.expect("installed free"),
                requested_bytes,
                armed: AtomicBool::new(true),
                matched_calls: AtomicUsize::new(0),
                failed_calls: AtomicUsize::new(0),
                observed_bytes: AtomicUsize::new(0),
                parent_bytes,
                parent_address: AtomicUsize::new(0),
                parent_freed: AtomicBool::new(false),
            }),
            _py: py,
        };
        let mut replacement = ffi::PyMemAllocatorEx {
            ctx: std::ptr::from_mut(&mut *guard.state).cast(),
            malloc: Some(hooked_malloc),
            calloc: Some(hooked_calloc),
            realloc: Some(hooked_realloc),
            free: Some(hooked_free),
        };
        // SAFETY: This serial native test holds the GIL and starts no other
        // interpreters. The context has a stable heap address. Every callback
        // delegates except one exact nonzero malloc; callbacks do not allocate,
        // panic or call Python. No fallible operation follows installation.
        unsafe {
            ffi::PyMem_SetAllocator(
                ffi::PyMemAllocatorDomain::PYMEM_DOMAIN_OBJ,
                &mut replacement,
            );
        }
        guard
    }

    fn snapshot(&self) -> FailureReceipt {
        FailureReceipt {
            requested_bytes: self.state.requested_bytes,
            matched_calls: self.state.matched_calls.load(Ordering::Relaxed),
            failed_calls: self.state.failed_calls.load(Ordering::Relaxed),
            observed_bytes: self.state.observed_bytes.load(Ordering::Relaxed),
            saved_allocator: allocator_identity(self.state.previous),
            parent_address: self.state.parent_address.load(Ordering::Relaxed),
            parent_freed: self.state.parent_freed.load(Ordering::Relaxed),
        }
    }

    fn finish(self) -> FailureReceipt {
        let receipt = self.snapshot();
        drop(self);
        receipt
    }
}

impl Drop for FailObjectAllocation<'_> {
    fn drop(&mut self) {
        let mut previous = self.state.previous;
        // SAFETY: Restore callbacks while the GIL is held, before Box releases
        // their context. Conversion has returned or is unwinding.
        unsafe {
            ffi::PyMem_SetAllocator(ffi::PyMemAllocatorDomain::PYMEM_DOMAIN_OBJ, &mut previous);
        }
    }
}

fn check_failure(py: Python<'_>, receipt: &FailureReceipt, error: &PyErr) {
    assert_eq!(allocator_identity(allocator()), receipt.saved_allocator);
    assert_eq!(receipt.matched_calls, 1);
    assert_eq!(receipt.failed_calls, 1);
    assert_eq!(receipt.observed_bytes, receipt.requested_bytes);
    assert!(!PyErr::occurred(py));
    assert!(error.is_instance_of::<PyMemoryError>(py));
}

/// Restore json.JSONDecodeError even if a native assertion unwinds.
struct ErrorFactory<'py> {
    module: Bound<'py, PyModule>,
    original: Bound<'py, PyAny>,
    active: bool,
}

impl<'py> ErrorFactory<'py> {
    fn install(py: Python<'py>, calls: Arc<AtomicUsize>) -> PyResult<Self> {
        let module = py.import("json")?;
        let original = module.getattr("JSONDecodeError")?;
        let replacement = PyCFunction::new_closure(
            py,
            None,
            None,
            move |_args, _kwargs| -> PyResult<Py<PyAny>> {
                calls.fetch_add(1, Ordering::Relaxed);
                Err(PyRuntimeError::new_err("test factory reached"))
            },
        )?;
        let guard = Self {
            module,
            original,
            active: true,
        };
        guard.module.setattr("JSONDecodeError", replacement)?;
        Ok(guard)
    }

    fn restore(&mut self) -> PyResult<()> {
        self.module.setattr("JSONDecodeError", &self.original)?;
        self.active = false;
        Ok(())
    }
}

impl Drop for ErrorFactory<'_> {
    fn drop(&mut self) {
        if !self.active {
            return;
        }
        if let Err(error) = self.restore() {
            error.write_unraisable(self.module.py(), Some(self.module.as_any()));
        }
    }
}

#[test]
fn error_document_allocation_failure_recovers() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let document = "!".repeat(4096);
        let warmup = super::ErrorDocument(&document).into_pyobject(py)?;
        assert_eq!(warmup.to_str()?, document);
        drop(warmup);
        assert!(!PyErr::occurred(py));
        let guard = FailObjectAllocation::unicode(py, &document);
        let result = super::ErrorDocument(&document).into_pyobject(py);
        let receipt = guard.finish();
        let error = result.expect_err("the exact Unicode allocation must fail");
        check_failure(py, &receipt, &error);
        drop(error);
        let recovered = super::ErrorDocument(&document).into_pyobject(py)?;
        assert_eq!(recovered.to_str()?, document);
        assert!(!PyErr::occurred(py));
        eprintln!(
            "ERROR_DOCUMENT_ALLOCATOR {{\"entry\":\"direct\",\"domain\":\"OBJ\",\"matched_calls\":{},\"failed_calls\":{},\"requested_bytes\":{},\"observed_bytes\":{},\"restored\":{},\"pending_error\":{},\"factory_calls\":null,\"recovered\":true}}",
            receipt.matched_calls,
            receipt.failed_calls,
            receipt.requested_bytes,
            receipt.observed_bytes,
            allocator_identity(allocator()) == receipt.saved_allocator,
            PyErr::occurred(py),
        );
        Ok(())
    })
}

#[test]
fn json_decode_error_allocation_failure_skips_factory_and_recovers() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let document = "!".repeat(4096);
        let message = "test invalid document";
        let calls = Arc::new(AtomicUsize::new(0));
        let mut factory = ErrorFactory::install(py, calls.clone())?;
        let warmup = crate::json_decode_error(py, message, &document, 0);
        assert!(warmup.is_instance_of::<PyRuntimeError>(py));
        assert_eq!(calls.load(Ordering::Relaxed), 1);
        calls.store(0, Ordering::Relaxed);
        drop(warmup);
        assert!(!PyErr::occurred(py));
        let guard = FailObjectAllocation::unicode(py, &document);
        let error = crate::json_decode_error(py, message, &document, 0);
        let receipt = guard.finish();
        check_failure(py, &receipt, &error);
        assert_eq!(calls.load(Ordering::Relaxed), 0);
        factory.restore()?;
        drop(error);
        let recovered = crate::json_decode_error(py, message, &document, 0);
        assert!(recovered.is_instance(py, &factory.original));
        assert_eq!(
            recovered.value(py).getattr("doc")?.extract::<String>()?,
            document
        );
        assert_eq!(
            recovered.value(py).getattr("msg")?.extract::<String>()?,
            message
        );
        assert_eq!(recovered.value(py).getattr("pos")?.extract::<usize>()?, 0);
        assert_eq!(calls.load(Ordering::Relaxed), 0);
        assert!(!PyErr::occurred(py));
        eprintln!(
            "ERROR_DOCUMENT_ALLOCATOR {{\"entry\":\"json_decode_error\",\"domain\":\"OBJ\",\"matched_calls\":{},\"failed_calls\":{},\"requested_bytes\":{},\"observed_bytes\":{},\"restored\":{},\"pending_error\":{},\"factory_calls\":{},\"recovered\":true}}",
            receipt.matched_calls,
            receipt.failed_calls,
            receipt.requested_bytes,
            receipt.observed_bytes,
            allocator_identity(allocator()) == receipt.saved_allocator,
            PyErr::occurred(py),
            calls.load(Ordering::Relaxed),
        );
        Ok(())
    })
}

#[test]
fn ascii_constructor_requires_classified_non_singleton_text() {
    for (input, accepted) in [
        (r#""""#, false),
        (r#""a""#, false),
        (r#""ab""#, true),
        (r#""\u0061\u0062""#, true),
        (r#""\u00e9""#, false),
        (r#""ab\u00e9""#, false),
        (r#""\ud83d\ude00""#, false),
    ] {
        let mut reader = jsonmodem::document::DocumentReader::new(input);
        let mut buffer = String::new();
        let decoded = reader.string_with_metadata(&mut buffer).unwrap();
        let text = super::AsciiText::from_decoded(&decoded);
        assert_eq!(text.is_some(), accepted, "{input}");
        if let Some(text) = text {
            assert!(text.0.is_ascii() && text.0.len() > 1);
            assert_eq!(text.0, decoded.as_str());
        }
    }
}

#[test]
fn error_constructor_preserves_length_and_ascii_conditions() {
    for (text, accepted) in [
        (String::new(), false),
        ("a".repeat(1023), false),
        ("a".repeat(1024), true),
        ("\u{e9}".repeat(1024), false),
        (format!("{}\u{e9}", "a".repeat(1024)), false),
    ] {
        assert_eq!(
            super::AsciiText::from_error_document(&text).is_some(),
            accepted
        );
    }
}

#[test]
fn numpy_output_allocation_failure_recovers() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let data = PyBytes::new(py, &[42; 1000]);
        let kind = PyString::new(py, "u").into_any();
        let unit = PyString::new(py, "").into_any();
        let encode = || {
            crate::numpy::_numpy_dumps(
                py,
                data.clone(),
                vec![1000],
                kind.clone(),
                1,
                unit.clone(),
                16,
                0,
            )
        };
        let expected = encode()?;
        let expected_bytes = expected.bind(py).downcast::<PyBytes>()?.as_bytes();
        assert_eq!(expected_bytes.len(), 3001);
        assert!(!PyErr::occurred(py));
        let guard = FailObjectAllocation::bytes(py, expected_bytes.len());
        let result = encode();
        let receipt = guard.finish();
        let error = result.expect_err("the exact NumPy output allocation must fail");
        check_failure(py, &receipt, &error);
        drop(error);
        let recovered = encode()?;
        assert_eq!(
            recovered.bind(py).downcast::<PyBytes>()?.as_bytes(),
            expected_bytes
        );
        assert!(!PyErr::occurred(py));
        Ok(())
    })
}

fn numeric_allocation_failure(document: &str) -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let expected = super::super::decode(py, document)?;
        let requested = expected
            .bind(py)
            .call_method0("__sizeof__")?
            .extract::<usize>()?;
        // Full collection clears CPython's float freelist before injection.
        py.import("gc")?.call_method0("collect")?;
        let guard = FailObjectAllocation::install(py, requested);
        let result = super::super::decode(py, document);
        let receipt = guard.finish();
        let error = result.expect_err("the decoded number allocation must fail");
        check_failure(py, &receipt, &error);
        drop(error);
        let recovered = super::super::decode(py, document)?;
        assert!(recovered.bind(py).eq(expected.bind(py))?);
        assert!(!PyErr::occurred(py));
        Ok(())
    })
}

#[test]
fn signed_integer_allocation_failure_recovers() -> PyResult<()> {
    // Multiple digits avoid the padded single-digit constructor allocation.
    numeric_allocation_failure("-2147483648")
}

#[test]
fn unsigned_integer_allocation_failure_recovers() -> PyResult<()> {
    numeric_allocation_failure("18446744073709551615")
}

#[test]
fn float_allocation_failure_recovers() -> PyResult<()> {
    numeric_allocation_failure("1.25")
}

fn event_tuple_allocation_failure(at_finish: bool) -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let class = py.get_type::<crate::events::PyJsonModemEvents>();
        let parser = class.call0()?;
        if at_finish {
            parser.call_method1("feed", ("0",))?;
        }
        let method = parser.getattr(if at_finish { "finish" } else { "feed" })?;
        let input = pyo3::types::PyString::new(py, "null ");
        let tuple = pyo3::types::PyTuple::new(py, [py.None(), py.None(), py.None()])?;
        let requested = py
            .import("sys")?
            .getattr("getsizeof")?
            .call1((&tuple,))?
            .extract::<usize>()?;
        drop(tuple);
        // Full collection clears tuple freelists before the exact-size failure.
        py.import("gc")?.call_method0("collect")?;
        let guard = FailObjectAllocation::install(py, requested);
        let result = if at_finish {
            method.call0()
        } else {
            method.call1((&input,))
        };
        let receipt = guard.finish();
        let error = result.expect_err("the event tuple allocation must fail");
        check_failure(py, &receipt, &error);
        drop(error);
        let recovered = class.call0()?.call_method1("feed", (&input,))?;
        let mut events = recovered.try_iter()?;
        let event = events.next().expect("one null event")?;
        assert!(event.eq(("null", py.None(), py.None()))?);
        assert!(events.next().is_none());
        assert!(!PyErr::occurred(py));
        Ok(())
    })
}

fn decode_container_allocation_failure(
    document: &str,
    target_document: &str,
    parent_document: Option<&str>,
) -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let expected = super::super::decode(py, document)?;
        let getsizeof = py.import("sys")?.getattr("getsizeof")?;
        let target = super::super::decode(py, target_document)?;
        let requested = getsizeof.call1((target.bind(py),))?.extract::<usize>()?;
        let parent_bytes = if let Some(document) = parent_document {
            let parent = super::super::decode(py, document)?;
            getsizeof.call1((parent.bind(py),))?.extract::<usize>()?
        } else {
            0
        };
        let collect = py.import("gc")?.getattr("collect")?;
        collect.call0()?;
        let guard = FailObjectAllocation::install_with_parent(py, requested, parent_bytes);
        let result = super::super::decode(py, document);
        let before_collection = guard.snapshot();
        // Released containers can remain on CPython's freelists until collection.
        let collected = collect.call0();
        let receipt = guard.finish();
        collected?;
        let error = result.expect_err("the initial container allocation must fail");
        eprintln!(
            "DECODE_CONTAINER_COUNTS requested={} before_collection={} after_collection={} failed_before={} failed_after={}",
            requested,
            before_collection.matched_calls,
            receipt.matched_calls,
            before_collection.failed_calls,
            receipt.failed_calls,
        );
        assert_eq!(allocator_identity(allocator()), receipt.saved_allocator);
        // Fetching the first error can initialize PyO3's exception classes.
        assert!(before_collection.matched_calls >= 1);
        assert_eq!(before_collection.failed_calls, 1);
        assert_eq!(before_collection.observed_bytes, requested);
        assert!(!PyErr::occurred(py));
        assert!(error.is_instance_of::<PyMemoryError>(py));
        assert_eq!(receipt.failed_calls, before_collection.failed_calls);
        if parent_document.is_some() {
            assert_ne!(receipt.parent_address, 0);
            assert!(
                receipt.parent_freed,
                "the failed child's parent must be released"
            );
        }
        drop(error);
        let recovered = super::super::decode(py, document)?;
        assert!(recovered.bind(py).eq(expected.bind(py))?);
        assert!(!PyErr::occurred(py));
        eprintln!(
            "DECODE_CONTAINER_ALLOCATION requested={} failed={} parent_observed={} parent_freed={} recovered=true",
            receipt.requested_bytes,
            receipt.failed_calls,
            receipt.parent_address != 0,
            receipt.parent_freed,
        );
        Ok(())
    })
}

#[test]
fn feed_event_tuple_allocation_failure_recovers() -> PyResult<()> {
    event_tuple_allocation_failure(false)
}

#[test]
fn finish_event_tuple_allocation_failure_recovers() -> PyResult<()> {
    event_tuple_allocation_failure(true)
}

#[test]
fn owned_tuple_allocation_failure_releases_prepared_owners() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        // This length is outside CPython's small-tuple freelist.
        let length = 37;
        let sample = crate::tuple_from_owned_items(
            py,
            (0..length).map(|_| py.None().into_bound(py)).collect(),
        )?;
        let requested = py
            .import("sys")?
            .getattr("getsizeof")?
            .call1((&sample,))?
            .extract::<usize>()?;
        drop(sample);
        let owner = pyo3::types::PyList::empty(py).into_any();
        let references = owner.get_refcnt();
        let items = (0..length).map(|_| owner.clone()).collect();
        py.import("gc")?.call_method0("collect")?;

        let guard = FailObjectAllocation::install(py, requested);
        let result = crate::tuple_from_owned_items(py, items);
        let receipt = guard.finish();
        let error = result.expect_err("the tuple allocation must fail");
        check_failure(py, &receipt, &error);
        assert_eq!(owner.get_refcnt(), references);
        drop(error);

        let recovered =
            crate::tuple_from_owned_items(py, (0..length).map(|_| owner.clone()).collect())?;
        assert_eq!(owner.get_refcnt(), references + length);
        drop(recovered);
        assert_eq!(owner.get_refcnt(), references);
        assert!(!PyErr::occurred(py));
        Ok(())
    })
}

#[test]
fn decode_container_allocation_root_list() -> PyResult<()> {
    decode_container_allocation_failure("[]", "[]", None)
}

#[test]
fn decode_container_allocation_root_dict() -> PyResult<()> {
    decode_container_allocation_failure("{}", "{}", None)
}

#[test]
fn decode_container_allocation_nested_list_releases_parent() -> PyResult<()> {
    decode_container_allocation_failure(r#"{"k":[]}"#, "[]", Some("{}"))
}

#[test]
fn decode_container_allocation_nested_dict_releases_parent() -> PyResult<()> {
    decode_container_allocation_failure("[{}]", "{}", Some("[]"))
}

#[test]
#[ignore = "requires NumPy and the matching jsonmodem Python helpers"]
fn numpy_scalar_then_dates_output_allocation_failure_recovers() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let fixture = PyModule::from_code(
            py,
            pyo3::ffi::c_str!(
                r#"
import json
import sys
from unittest.mock import patch

import numpy as np
from jsonmodem import _compat, _numpy

def prepare(native):
    text = [
        "2000-02-28T01:02:03.123456",
        "2000-02-28T04:05:06.000001",
        "2000-02-29T00:00:00",
    ] * 100
    fresh_text = [
        "2024-03-01T12:30:00.654321",
        "2024-03-01T00:00:00",
        "2024-03-02T08:09:10.000001",
    ]
    dates = np.array(text, dtype="datetime64[us]")
    fresh_dates = np.array(fresh_text, dtype="datetime64[us]")
    scalar = np.int64(7)
    scalar_types = _numpy.SCALAR_TYPES
    table = native._NumericScalarTypes(np, scalar_types)
    special = _compat._ENCODER_HELPERS[3]
    defaults = (
        sys.modules, _numpy, native, np, _numpy.encode,
        special, native._numpy_dumps, scalar_types,
    )
    def encoded(value):
        return json.dumps(value, separators=(",", ":")).encode("ascii")
    return {
        "module": _numpy,
        "original_native": _numpy.native,
        "context": patch.object(_numpy, "native", native),
        "helpers": _compat._ENCODER_HELPERS[:12] + (table, defaults),
        "scalar": scalar,
        "value": [scalar, dates],
        "fresh_value": [np.int64(13), fresh_dates],
        "expected_dates": encoded(text),
        "expected": encoded([7, text]),
        "expected_fresh": encoded([13, fresh_text]),
        "input_bytes": dates.nbytes,
    }
"#
            ),
            pyo3::ffi::c_str!("numpy_scalar_day_prefix_allocation_fixture.py"),
            pyo3::ffi::c_str!("numpy_scalar_day_prefix_allocation_fixture"),
        )?;

        // Use this test binary's class and function, not a second extension's
        // PyO3 class identity. The Python serialization helpers remain unchanged.
        let native = PyModule::new(py, "_numpy_scalar_day_prefix_test_native")?;
        native.add_function(pyo3::wrap_pyfunction!(crate::numpy::_numpy_dumps, &native)?)?;
        native.add_class::<crate::numpy::NumericScalarTypes>()?;
        let setup = fixture.getattr("prepare")?.call1((&native,))?;
        let module = setup.get_item("module")?;
        let original_native = setup.get_item("original_native")?;
        let context = setup.get_item("context")?;
        context.call_method0("__enter__")?;

        // Restore the Python helper even if a native assertion unwinds.
        let outcome = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> PyResult<()> {
            let helpers = setup
                .get_item("helpers")?
                .downcast_into::<pyo3::types::PyTuple>()?;
            let types = helpers
                .get_item(12)?
                .downcast_into::<crate::numpy::NumericScalarTypes>()?;
            let defaults = helpers
                .get_item(13)?
                .downcast_into::<pyo3::types::PyTuple>()?;
            let scalar = setup.get_item("scalar")?;
            assert!(matches!(
                types
                    .get()
                    .read(&scalar, &defaults, &helpers.get_item(3)?)?,
                Some(crate::numpy::ScalarValue::Signed(7))
            ));

            let value = setup.get_item("value")?;
            let fresh_value = setup.get_item("fresh_value")?;
            let expected_dates = setup
                .get_item("expected_dates")?
                .downcast_into::<PyBytes>()?;
            let expected = setup.get_item("expected")?.downcast_into::<PyBytes>()?;
            let expected_fresh = setup
                .get_item("expected_fresh")?
                .downcast_into::<PyBytes>()?;
            let target_length = expected_dates.as_bytes().len();
            assert_eq!(target_length, 8001);
            assert_ne!(
                target_length,
                setup.get_item("input_bytes")?.extract::<usize>()?
            );
            assert_ne!(target_length, expected.as_bytes().len());
            let encode = |value| {
                crate::compat::_dumps_objects(
                    py,
                    value,
                    py.None().into_bound(py),
                    16,
                    false,
                    helpers.clone(),
                )
            };
            let control = encode(value.clone())?;
            assert_eq!(control.bind(py).as_bytes(), expected.as_bytes());
            drop(control);
            assert!(!PyErr::occurred(py));

            let guard = FailObjectAllocation::bytes(py, target_length);
            let result = encode(value);
            let receipt = guard.finish();
            let error = result.expect_err("the date-array bytes allocation must fail");
            check_failure(py, &receipt, &error);
            drop(error);

            let recovered = encode(fresh_value)?;
            assert_eq!(recovered.bind(py).as_bytes(), expected_fresh.as_bytes());
            assert!(!PyErr::occurred(py));
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

#[cfg(not(Py_3_13))]
#[test]
#[ignore = "requires NumPy and the matching jsonmodem Python helpers"]
fn numpy_root_output_allocation_failure_recovers() -> PyResult<()> {
    numpy_root_output_allocation_failure(false)
}

#[cfg(not(Py_3_13))]
#[test]
#[ignore = "requires NumPy and the matching jsonmodem Python helpers"]
fn numpy_root_dict_output_allocation_failure_recovers() -> PyResult<()> {
    numpy_root_output_allocation_failure(true)
}

#[cfg(not(Py_3_13))]
fn numpy_root_output_allocation_failure(dictionaries: bool) -> PyResult<()> {
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
    scalar = np.int64(7)
    values = [scalar] * 1024
    fresh_values = [np.int64(13)] * 1024
    expected = b"[" + b",".join([b"7"] * 1024) + b"]"
    expected_fresh = b"[" + b",".join([b"13"] * 1024) + b"]"
    roots = (values, tuple(values))
    fresh_roots = (fresh_values, tuple(fresh_values))
    if dictionaries:
        keys = [f"key_{index:03}" for index in range(128)]
        roots = ({key: scalar for key in keys},)
        fresh_roots = ({key: np.int64(13) for key in keys},)
        expected = b"{" + b",".join(b'"' + key.encode() + b'":7' for key in keys) + b"}"
        expected_fresh = b"{" + b",".join(b'"' + key.encode() + b'":13' for key in keys) + b"}"
    return {
        "module": _numpy,
        "original_native": _numpy.native,
        "context": patch.object(_numpy, "native", native),
        "helpers": _compat._ENCODER_HELPERS[:12] + (table, defaults),
        "scalar": scalar,
        "values": roots,
        "fresh_values": fresh_roots,
        "expected": expected,
        "expected_fresh": expected_fresh,
    }
"#
            ),
            pyo3::ffi::c_str!("numpy_root_allocation_fixture.py"),
            pyo3::ffi::c_str!("numpy_root_allocation_fixture"),
        )?;
        let native = PyModule::new(py, "_numpy_root_test_native")?;
        native.add_function(pyo3::wrap_pyfunction!(crate::numpy::_numpy_dumps, &native)?)?;
        native.add_class::<crate::numpy::NumericScalarTypes>()?;
        let setup = fixture.getattr("prepare")?.call1((&native, dictionaries))?;
        let module = setup.get_item("module")?;
        let original_native = setup.get_item("original_native")?;
        let context = setup.get_item("context")?;
        context.call_method0("__enter__")?;

        // The local type table and C function belong to this executable. Restore
        // the Python helper and allocator before reporting a native assertion.
        let outcome = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| -> PyResult<()> {
            let helpers = setup
                .get_item("helpers")?
                .downcast_into::<pyo3::types::PyTuple>()?;
            let types = helpers
                .get_item(12)?
                .downcast_into::<crate::numpy::NumericScalarTypes>()?;
            let defaults = helpers
                .get_item(13)?
                .downcast_into::<pyo3::types::PyTuple>()?;
            let queries = types
                .get()
                .root_query_names()
                .expect("prepared root queries");
            assert_eq!(queries[0].bind(py).to_str()?, "jsonmodem._numpy");
            let scalar = setup.get_item("scalar")?;
            assert!(matches!(
                types
                    .get()
                    .read(&scalar, &defaults, &helpers.get_item(3)?)?,
                Some(crate::numpy::ScalarValue::Signed(7))
            ));
            let values = setup
                .get_item("values")?
                .downcast_into::<pyo3::types::PyTuple>()?;
            let fresh_values = setup
                .get_item("fresh_values")?
                .downcast_into::<pyo3::types::PyTuple>()?;
            let expected = setup.get_item("expected")?.downcast_into::<PyBytes>()?;
            let expected_fresh = setup
                .get_item("expected_fresh")?
                .downcast_into::<PyBytes>()?;
            assert!(expected.as_bytes().len() > 1024);
            let encode = |value| {
                crate::compat::_dumps_objects(
                    py,
                    value,
                    py.None().into_bound(py),
                    16,
                    false,
                    helpers.clone(),
                )
            };
            for (value, fresh_value) in values.iter().zip(fresh_values.iter()) {
                let control = encode(value.clone())?;
                assert_eq!(control.bind(py).as_bytes(), expected.as_bytes());
                drop(control);
                assert!(!PyErr::occurred(py));

                let guard = FailObjectAllocation::bytes(py, expected.as_bytes().len());
                let result = encode(value);
                let receipt = guard.finish();
                let error = result.expect_err("root publication must fail without a retry");
                check_failure(py, &receipt, &error);
                drop(error);

                let recovered = encode(fresh_value)?;
                assert_eq!(recovered.bind(py).as_bytes(), expected_fresh.as_bytes());
                assert!(!PyErr::occurred(py));
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
