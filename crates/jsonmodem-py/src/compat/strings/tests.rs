//! Exercise the error-document constructor with one real object-allocation
//! failure.

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
    types::{PyCFunction, PyModule},
};

type Malloc = extern "C" fn(*mut c_void, usize) -> *mut c_void;
type Calloc = extern "C" fn(*mut c_void, usize, usize) -> *mut c_void;
type Realloc = extern "C" fn(*mut c_void, *mut c_void, usize) -> *mut c_void;
type Free = extern "C" fn(*mut c_void, *mut c_void);

/// Delegate to the saved allocator except for one exact Unicode allocation.
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
    (hook.malloc)(hook.previous.ctx, size)
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
struct FailUnicode<'py> {
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
}

impl<'py> FailUnicode<'py> {
    fn install(py: Python<'py>, document: &str) -> Self {
        assert!(document.len() >= 1024 && document.is_ascii());
        let requested_bytes = size_of::<ffi::PyASCIIObject>()
            .checked_add(document.len())
            .and_then(|size| size.checked_add(1))
            .expect("ASCII object allocation fits usize");
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

    fn finish(self) -> FailureReceipt {
        let receipt = FailureReceipt {
            requested_bytes: self.state.requested_bytes,
            matched_calls: self.state.matched_calls.load(Ordering::Relaxed),
            failed_calls: self.state.failed_calls.load(Ordering::Relaxed),
            observed_bytes: self.state.observed_bytes.load(Ordering::Relaxed),
            saved_allocator: allocator_identity(self.state.previous),
        };
        drop(self);
        receipt
    }
}

impl Drop for FailUnicode<'_> {
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
        let guard = FailUnicode::install(py, &document);
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
        let guard = FailUnicode::install(py, &document);
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
