//! Check ownership against the original append on real CPython lists.

#![cfg(all(
    Py_3_12,
    not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
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
    mem::{MaybeUninit, align_of, offset_of, size_of},
    sync::{
        Arc,
        atomic::{AtomicBool, AtomicUsize, Ordering},
    },
};

use pyo3::{
    exceptions::{PyMemoryError, PyValueError},
    ffi,
    prelude::*,
    types::{PyCFunction, PyDict, PyList, PyTuple},
};

/// Count finalization without running Python or allocating in the destructor.
#[pyclass]
struct TrackedValue {
    finalized: Arc<AtomicUsize>,
}

impl Drop for TrackedValue {
    fn drop(&mut self) {
        self.finalized.fetch_add(1, Ordering::Relaxed);
    }
}

fn tracked(py: Python<'_>) -> PyResult<(PyObject, Arc<AtomicUsize>)> {
    let finalized = Arc::new(AtomicUsize::new(0));
    let value = Py::new(
        py,
        TrackedValue {
            finalized: finalized.clone(),
        },
    )?;
    assert_eq!(value.get_refcnt(py), 1);
    Ok((value.into_any(), finalized))
}

/// Run the same ownership checks with the original and proposed operation.
#[derive(Clone, Copy, Debug)]
enum Appender {
    Reference,
    Adapter,
}

impl Appender {
    fn append(self, list: &Bound<'_, PyList>, value: PyObject) -> PyResult<()> {
        match self {
            Self::Reference => list.append(value),
            Self::Adapter => super::append(list, value),
        }
    }

    fn name(self) -> &'static str {
        match self {
            Self::Reference => "reference",
            Self::Adapter => "adapter",
        }
    }
}

fn run_both(test: impl for<'py> Fn(Python<'py>, Appender) -> PyResult<()>) -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        for appender in [Appender::Reference, Appender::Adapter] {
            test(py, appender)?;
        }
        Ok(())
    })
}

/// Saved fields are compared after mutation, never used to access old storage.
#[derive(Clone, Copy, Debug, PartialEq)]
struct Storage {
    length: isize,
    allocated: isize,
    items: *mut *mut ffi::PyObject,
}

fn storage(list: &Bound<'_, PyList>) -> Storage {
    // SAFETY: this module is restricted to the declared GIL-only CPython ABI.
    // list owns the object while its initialized header fields are read.
    unsafe {
        let object = list.as_ptr().cast::<ffi::PyListObject>();
        Storage {
            length: (*object).ob_base.ob_size,
            allocated: (*object).allocated,
            items: (*object).ob_item,
        }
    }
}

fn member(list: &Bound<'_, PyList>, index: usize, expected: *mut ffi::PyObject) -> PyResult<()> {
    assert_eq!(list.get_item(index)?.as_ptr(), expected);
    Ok(())
}

#[test]
fn declared_layout_matches_installed_headers() {
    assert_eq!(size_of::<*mut ffi::PyObject>(), 8);
    assert_eq!(size_of::<ffi::Py_ssize_t>(), 8);
    assert_eq!(size_of::<ffi::PyObject>(), 16);
    assert_eq!(size_of::<ffi::PyVarObject>(), 24);
    assert_eq!(offset_of!(ffi::PyVarObject, ob_size), 16);
    assert_eq!(size_of::<ffi::PyListObject>(), 40);
    assert_eq!(align_of::<ffi::PyListObject>(), 8);
    assert_eq!(offset_of!(ffi::PyListObject, ob_base), 0);
    assert_eq!(offset_of!(ffi::PyListObject, ob_item), 24);
    assert_eq!(offset_of!(ffi::PyListObject, allocated), 32);
    assert_eq!(size_of::<ffi::PyMemAllocatorEx>(), 40);
    assert_eq!(offset_of!(ffi::PyMemAllocatorEx, ctx), 0);
    assert_eq!(offset_of!(ffi::PyMemAllocatorEx, malloc), 8);
    assert_eq!(offset_of!(ffi::PyMemAllocatorEx, calloc), 16);
    assert_eq!(offset_of!(ffi::PyMemAllocatorEx, realloc), 24);
    assert_eq!(offset_of!(ffi::PyMemAllocatorEx, free), 32);
}

#[test]
fn growth_matches_original_append() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let original = PyList::empty(py);
        let actual = PyList::empty(py);
        let (value, finalized) = tracked(py)?;
        assert_eq!(storage(&actual).allocated, 0);
        for index in 0..129 {
            let before = storage(&actual);
            original.append(value.clone_ref(py))?;
            super::append(&actual, value.clone_ref(py))?;
            let expected = storage(&original);
            let after = storage(&actual);
            assert_eq!(after.length, expected.length);
            assert_eq!(after.allocated, expected.allocated);
            if before.length < before.allocated {
                assert_eq!(after.items, before.items);
            }
            member(&actual, index, value.as_ptr())?;
            member(&original, index, value.as_ptr())?;
            assert_eq!(value.get_refcnt(py), 1 + 2 * (index as isize + 1));
        }
        drop(original);
        drop(actual);
        assert_eq!(value.get_refcnt(py), 1);
        assert_eq!(finalized.load(Ordering::Relaxed), 0);
        drop(value);
        assert_eq!(finalized.load(Ordering::Relaxed), 1);
        Ok(())
    })
}

#[test]
fn spare_append_transfers_non_immortal_owner() -> PyResult<()> {
    run_both(|py, appender| {
        let list = PyList::empty(py);
        list.append(py.None())?;
        let before = storage(&list);
        assert!(before.allocated > before.length);
        let (value, finalized) = tracked(py)?;
        let pointer = value.as_ptr();
        appender.append(&list, value)?;
        assert_eq!(storage(&list).items, before.items);
        assert_eq!(storage(&list).allocated, before.allocated);
        assert_eq!(list.len(), 2);
        let saved = list.get_item(1)?;
        assert_eq!(saved.as_ptr(), pointer);
        assert_eq!(saved.get_refcnt(), 2);
        drop(saved);
        assert_eq!(finalized.load(Ordering::Relaxed), 0);
        drop(list);
        assert_eq!(finalized.load(Ordering::Relaxed), 1);
        Ok(())
    })
}

#[test]
fn repeated_references_keep_one_owner_per_entry() -> PyResult<()> {
    run_both(|py, appender| {
        let list = PyList::empty(py);
        let (value, finalized) = tracked(py)?;
        for count in 1..=64 {
            appender.append(&list, value.clone_ref(py))?;
            assert_eq!(value.get_refcnt(py), count + 1);
        }
        drop(list);
        assert_eq!(value.get_refcnt(py), 1);
        assert_eq!(finalized.load(Ordering::Relaxed), 0);
        drop(value);
        assert_eq!(finalized.load(Ordering::Relaxed), 1);
        Ok(())
    })
}

#[test]
fn self_reference_survives_until_cleared() -> PyResult<()> {
    run_both(|py, appender| {
        let list = PyList::empty(py);
        let (value, finalized) = tracked(py)?;
        list.append(value)?;
        assert_eq!(list.get_refcnt(), 1);
        assert!(storage(&list).allocated > 1);
        appender.append(&list, list.clone().into_any().unbind())?;
        assert_eq!(list.get_refcnt(), 2);
        member(&list, 1, list.as_ptr())?;
        assert_eq!(list.get_refcnt(), 2);
        list.del_slice(0, list.len())?;
        assert_eq!(list.get_refcnt(), 1);
        assert_eq!(list.len(), 0);
        assert_eq!(finalized.load(Ordering::Relaxed), 1);
        Ok(())
    })
}

#[test]
fn clear_between_calls_uses_current_storage() -> PyResult<()> {
    run_both(|py, appender| {
        let list = PyList::empty(py);
        let (first, first_finalized) = tracked(py)?;
        appender.append(&list, first)?;
        list.del_slice(0, list.len())?;
        assert_eq!(first_finalized.load(Ordering::Relaxed), 1);
        assert_eq!(storage(&list).length, 0);
        assert_eq!(storage(&list).allocated, 0);
        assert!(storage(&list).items.is_null());
        let (second, second_finalized) = tracked(py)?;
        let pointer = second.as_ptr();
        appender.append(&list, second)?;
        assert_eq!(list.len(), 1);
        member(&list, 0, pointer)?;
        drop(list);
        assert_eq!(first_finalized.load(Ordering::Relaxed), 1);
        assert_eq!(second_finalized.load(Ordering::Relaxed), 1);
        Ok(())
    })
}

#[test]
fn shrink_between_calls_uses_current_length() -> PyResult<()> {
    run_both(|py, appender| {
        let list = PyList::empty(py);
        let (first, first_finalized) = tracked(py)?;
        for _ in 0..32 {
            appender.append(&list, first.clone_ref(py))?;
        }
        let before = storage(&list);
        assert_eq!(first.get_refcnt(py), 33);
        list.del_slice(1, list.len())?;
        assert_eq!(first.get_refcnt(py), 2);
        let shrunk = storage(&list);
        assert_eq!(shrunk.length, 1);
        assert!(shrunk.allocated < before.allocated);
        assert!(shrunk.allocated > 1);
        let (second, second_finalized) = tracked(py)?;
        let second_pointer = second.as_ptr();
        appender.append(&list, second)?;
        assert_eq!(list.len(), 2);
        assert_eq!(storage(&list).items, shrunk.items);
        member(&list, 0, first.as_ptr())?;
        member(&list, 1, second_pointer)?;
        assert_eq!(first.get_refcnt(py), 2);
        drop(list);
        assert_eq!(first.get_refcnt(py), 1);
        assert_eq!(second_finalized.load(Ordering::Relaxed), 1);
        drop(first);
        assert_eq!(first_finalized.load(Ordering::Relaxed), 1);
        Ok(())
    })
}

#[test]
fn growth_between_calls_uses_current_storage() -> PyResult<()> {
    run_both(|py, appender| {
        let list = PyList::empty(py);
        let (first, first_finalized) = tracked(py)?;
        appender.append(&list, first.clone_ref(py))?;
        let before = storage(&list);
        for _ in 0..256 {
            list.append(first.clone_ref(py))?;
        }
        assert!(storage(&list).allocated > before.allocated);
        let (last, last_finalized) = tracked(py)?;
        let pointer = last.as_ptr();
        appender.append(&list, last)?;
        assert_eq!(list.len(), 258);
        member(&list, 0, first.as_ptr())?;
        member(&list, 257, pointer)?;
        assert_eq!(first.get_refcnt(py), 258);
        drop(list);
        assert_eq!(first.get_refcnt(py), 1);
        assert_eq!(last_finalized.load(Ordering::Relaxed), 1);
        drop(first);
        assert_eq!(first_finalized.load(Ordering::Relaxed), 1);
        Ok(())
    })
}

#[test]
fn replacement_between_calls_keeps_live_owners() -> PyResult<()> {
    run_both(|py, appender| {
        let list = PyList::empty(py);
        let (first, first_finalized) = tracked(py)?;
        appender.append(&list, first)?;
        let (replacement, replacement_finalized) = tracked(py)?;
        let replacement_pointer = replacement.as_ptr();
        list.set_item(0, replacement)?;
        assert_eq!(first_finalized.load(Ordering::Relaxed), 1);
        let (next, next_finalized) = tracked(py)?;
        let next_pointer = next.as_ptr();
        appender.append(&list, next)?;
        assert_eq!(list.len(), 2);
        member(&list, 0, replacement_pointer)?;
        member(&list, 1, next_pointer)?;
        assert_eq!(replacement_finalized.load(Ordering::Relaxed), 0);
        assert_eq!(next_finalized.load(Ordering::Relaxed), 0);
        drop(list);
        assert_eq!(first_finalized.load(Ordering::Relaxed), 1);
        assert_eq!(replacement_finalized.load(Ordering::Relaxed), 1);
        assert_eq!(next_finalized.load(Ordering::Relaxed), 1);
        Ok(())
    })
}

#[test]
fn sort_callback_keeps_refusal_and_cleanup() -> PyResult<()> {
    run_both(|py, appender| {
        let list = PyList::new(py, [3_i64, 1, 2])?;
        let owner = list.clone().unbind();
        let calls = Arc::new(AtomicUsize::new(0));
        let finalized = Arc::new(AtomicUsize::new(0));
        let callback_calls = calls.clone();
        let callback_finalized = finalized.clone();
        let key = PyCFunction::new_closure(
            py,
            None,
            None,
            move |args: &Bound<'_, PyTuple>, _kwargs: Option<&Bound<'_, PyDict>>| {
                let py = args.py();
                if callback_calls.fetch_add(1, Ordering::Relaxed) == 0 {
                    let list = owner.bind(py);
                    let before = storage(list);
                    assert_eq!(before.length, 0);
                    assert_eq!(before.allocated, -1);
                    assert!(before.items.is_null());
                    let value = Py::new(
                        py,
                        TrackedValue {
                            finalized: callback_finalized.clone(),
                        },
                    )?;
                    appender.append(list, value.into_any())?;
                    assert_eq!(list.len(), 1);
                    assert!(storage(list).allocated > 0);
                    assert_eq!(callback_finalized.load(Ordering::Relaxed), 0);
                }
                args.get_item(0)?.extract::<i64>()
            },
        )?;
        let kwargs = PyDict::new(py);
        kwargs.set_item("key", &key)?;
        let error = list.call_method("sort", (), Some(&kwargs)).unwrap_err();
        assert!(error.is_instance_of::<PyValueError>(py));
        assert_eq!(
            error.value(py).str()?.to_str()?,
            "list modified during sort"
        );
        assert_eq!(calls.load(Ordering::Relaxed), 3);
        assert_eq!(finalized.load(Ordering::Relaxed), 1);
        assert_eq!(list.extract::<Vec<i64>>()?, [1, 2, 3]);
        Ok(())
    })
}

type Malloc = extern "C" fn(*mut c_void, usize) -> *mut c_void;
type Calloc = extern "C" fn(*mut c_void, usize, usize) -> *mut c_void;
type Realloc = extern "C" fn(*mut c_void, *mut c_void, usize) -> *mut c_void;
type Free = extern "C" fn(*mut c_void, *mut c_void);

/// Wrap the saved allocator, rejecting only one exact list-storage resize.
struct HookState {
    previous: ffi::PyMemAllocatorEx,
    malloc: Malloc,
    calloc: Calloc,
    realloc: Realloc,
    free: Free,
    target: usize,
    requested_bytes: usize,
    armed: AtomicBool,
    matched_calls: AtomicUsize,
    failed_calls: AtomicUsize,
    observed_address: AtomicUsize,
    observed_bytes: AtomicUsize,
}

extern "C" fn hooked_malloc(context: *mut c_void, size: usize) -> *mut c_void {
    // SAFETY: the guard keeps this immutable context live until restoration.
    let hook = unsafe { &*context.cast::<HookState>() };
    (hook.malloc)(hook.previous.ctx, size)
}

extern "C" fn hooked_calloc(context: *mut c_void, count: usize, size: usize) -> *mut c_void {
    // SAFETY: the guard keeps this immutable context live until restoration.
    let hook = unsafe { &*context.cast::<HookState>() };
    (hook.calloc)(hook.previous.ctx, count, size)
}

extern "C" fn hooked_realloc(
    context: *mut c_void,
    pointer: *mut c_void,
    size: usize,
) -> *mut c_void {
    // SAFETY: the guard keeps this context live; mutable counters are atomic.
    let hook = unsafe { &*context.cast::<HookState>() };
    if pointer.addr() == hook.target && size == hook.requested_bytes {
        hook.matched_calls.fetch_add(1, Ordering::Relaxed);
        hook.observed_address
            .store(pointer.addr(), Ordering::Relaxed);
        hook.observed_bytes.store(size, Ordering::Relaxed);
        if hook.armed.swap(false, Ordering::Relaxed) {
            hook.failed_calls.fetch_add(1, Ordering::Relaxed);
            return std::ptr::null_mut();
        }
    }
    (hook.realloc)(hook.previous.ctx, pointer, size)
}

extern "C" fn hooked_free(context: *mut c_void, pointer: *mut c_void) {
    // SAFETY: the guard keeps this immutable context live until restoration.
    let hook = unsafe { &*context.cast::<HookState>() };
    (hook.free)(hook.previous.ctx, pointer);
}

fn allocator() -> ffi::PyMemAllocatorEx {
    let mut saved = MaybeUninit::uninit();
    // SAFETY: this output is valid storage for the complete allocator record.
    // All callers hold the GIL in this serial native test process.
    unsafe {
        ffi::PyMem_GetAllocator(
            ffi::PyMemAllocatorDomain::PYMEM_DOMAIN_MEM,
            saved.as_mut_ptr(),
        );
        saved.assume_init()
    }
}

fn allocator_identity(allocator: ffi::PyMemAllocatorEx) -> [usize; 5] {
    [
        allocator.ctx.addr(),
        allocator.malloc.map_or(0, |callback| callback as usize),
        allocator.calloc.map_or(0, |callback| callback as usize),
        allocator.realloc.map_or(0, |callback| callback as usize),
        allocator.free.map_or(0, |callback| callback as usize),
    ]
}

/// Restore the allocator before releasing the context, including on unwind.
struct FailGrowth<'py> {
    state: Box<HookState>,
    _py: Python<'py>,
}

/// Observations copied after the append and checked only after restoration.
struct FailureReceipt {
    target: usize,
    requested_bytes: usize,
    matched_calls: usize,
    failed_calls: usize,
    observed_address: usize,
    observed_bytes: usize,
    saved_allocator: [usize; 5],
}

impl<'py> FailGrowth<'py> {
    fn install(list: &Bound<'py, PyList>, requested_bytes: usize) -> Self {
        let current = storage(list);
        assert_eq!(current.length, 4);
        assert_eq!(current.allocated, 4);
        assert!(!current.items.is_null());
        assert_eq!(requested_bytes, 8 * size_of::<*mut ffi::PyObject>());
        let previous = allocator();
        let mut guard = Self {
            state: Box::new(HookState {
                malloc: previous.malloc.expect("installed malloc"),
                calloc: previous.calloc.expect("installed calloc"),
                realloc: previous.realloc.expect("installed realloc"),
                free: previous.free.expect("installed free"),
                previous,
                target: current.items.addr(),
                requested_bytes,
                armed: AtomicBool::new(true),
                matched_calls: AtomicUsize::new(0),
                failed_calls: AtomicUsize::new(0),
                observed_address: AtomicUsize::new(0),
                observed_bytes: AtomicUsize::new(0),
            }),
            _py: list.py(),
        };
        let mut replacement = ffi::PyMemAllocatorEx {
            ctx: std::ptr::from_mut(&mut *guard.state).cast(),
            malloc: Some(hooked_malloc),
            calloc: Some(hooked_calloc),
            realloc: Some(hooked_realloc),
            free: Some(hooked_free),
        };
        // SAFETY: this owned, serial process holds the GIL and starts no other
        // interpreters. Every callback delegates to the saved allocator except
        // the one exact nonzero resize. Its context has a stable heap address.
        // There are no fallible operations after installation before return.
        unsafe {
            ffi::PyMem_SetAllocator(
                ffi::PyMemAllocatorDomain::PYMEM_DOMAIN_MEM,
                &mut replacement,
            );
        }
        guard
    }

    fn finish(self) -> FailureReceipt {
        let receipt = FailureReceipt {
            target: self.state.target,
            requested_bytes: self.state.requested_bytes,
            matched_calls: self.state.matched_calls.load(Ordering::Relaxed),
            failed_calls: self.state.failed_calls.load(Ordering::Relaxed),
            observed_address: self.state.observed_address.load(Ordering::Relaxed),
            observed_bytes: self.state.observed_bytes.load(Ordering::Relaxed),
            saved_allocator: allocator_identity(self.state.previous),
        };
        drop(self);
        receipt
    }
}

impl Drop for FailGrowth<'_> {
    fn drop(&mut self) {
        let mut previous = self.state.previous;
        // SAFETY: the GIL remains held and the append has returned or unwound.
        // Restore callbacks before Box drops the context they formerly used.
        unsafe {
            ffi::PyMem_SetAllocator(ffi::PyMemAllocatorDomain::PYMEM_DOMAIN_MEM, &mut previous);
        }
    }
}

#[test]
fn growth_failure_preserves_members_and_recovers() -> PyResult<()> {
    run_both(|py, appender| {
        let (existing, existing_finalized) = tracked(py)?;
        let list = PyList::new(py, (0..4).map(|_| existing.clone_ref(py)))?;
        let before = storage(&list);
        assert_eq!(existing.get_refcnt(py), 5);
        let (failed, failed_finalized) = tracked(py)?;
        let guard = FailGrowth::install(&list, 8 * size_of::<*mut ffi::PyObject>());
        let result = appender.append(&list, failed);
        let receipt = guard.finish();
        assert_eq!(allocator_identity(allocator()), receipt.saved_allocator);
        assert_eq!(receipt.matched_calls, 1);
        assert_eq!(receipt.failed_calls, 1);
        assert_eq!(receipt.observed_address, before.items.addr());
        assert_eq!(receipt.observed_bytes, 64);
        let error = result.unwrap_err();
        assert!(error.is_instance_of::<PyMemoryError>(py));
        assert_eq!(storage(&list), before);
        assert_eq!(list.len(), 4);
        for index in 0..4 {
            member(&list, index, existing.as_ptr())?;
        }
        assert_eq!(existing.get_refcnt(py), 5);
        assert_eq!(existing_finalized.load(Ordering::Relaxed), 0);
        assert_eq!(failed_finalized.load(Ordering::Relaxed), 1);
        drop(error);
        let (recovered, recovered_finalized) = tracked(py)?;
        let recovered_pointer = recovered.as_ptr();
        appender.append(&list, recovered)?;
        assert_eq!(list.len(), 5);
        assert_eq!(storage(&list).allocated, 8);
        for index in 0..4 {
            member(&list, index, existing.as_ptr())?;
        }
        member(&list, 4, recovered_pointer)?;
        assert_eq!(existing.get_refcnt(py), 5);
        drop(list);
        assert_eq!(existing.get_refcnt(py), 1);
        assert_eq!(recovered_finalized.load(Ordering::Relaxed), 1);
        drop(existing);
        assert_eq!(existing_finalized.load(Ordering::Relaxed), 1);
        eprintln!(
            "LIST_APPEND_ALLOCATOR {{\"implementation\":\"{}\",\"target_address\":{},\"requested_bytes\":{},\"observed_address\":{},\"observed_bytes\":{},\"matched_calls\":{},\"failed_calls\":{},\"restored\":true,\"recovered_length\":5,\"failed_value_finalized\":1}}",
            appender.name(),
            receipt.target,
            receipt.requested_bytes,
            receipt.observed_address,
            receipt.observed_bytes,
            receipt.matched_calls,
            receipt.failed_calls,
        );
        Ok(())
    })
}

#[test]
fn nested_list_members_remain_independent() -> PyResult<()> {
    run_both(|py, appender| {
        let outer = PyList::empty(py);
        let left = PyList::empty(py);
        let right = PyList::empty(py);
        let (left_value, left_finalized) = tracked(py)?;
        let (right_value, right_finalized) = tracked(py)?;
        left.append(left_value)?;
        right.append(right_value)?;
        appender.append(&outer, left.clone().into_any().unbind())?;
        appender.append(&outer, right.clone().into_any().unbind())?;
        left.append(py.None())?;
        assert_eq!(left.len(), 2);
        assert_eq!(right.len(), 1);
        member(&outer, 0, left.as_ptr())?;
        member(&outer, 1, right.as_ptr())?;
        assert_eq!(left.get_refcnt(), 2);
        assert_eq!(right.get_refcnt(), 2);
        drop(outer);
        assert_eq!(left.get_refcnt(), 1);
        assert_eq!(right.get_refcnt(), 1);
        assert_eq!(left_finalized.load(Ordering::Relaxed), 0);
        assert_eq!(right_finalized.load(Ordering::Relaxed), 0);
        drop(left);
        drop(right);
        assert_eq!(left_finalized.load(Ordering::Relaxed), 1);
        assert_eq!(right_finalized.load(Ordering::Relaxed), 1);
        Ok(())
    })
}
