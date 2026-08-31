//! Explicit collection tests callbacks even when automatic GC is deferred.

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

use std::sync::{
    Arc,
    atomic::{AtomicUsize, Ordering},
};

use pyo3::{ffi, ffi::c_str, prelude::*, types::PyList};

/// Count owners released by mutation without running another Python callback.
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
    Ok((value.into_any(), finalized))
}

/// Compare header fields without accessing the storage saved before a callback.
#[derive(Clone, Copy)]
struct Storage {
    length: isize,
    allocated: isize,
    items: *mut *mut ffi::PyObject,
}

fn storage(list: &Bound<'_, PyList>) -> Storage {
    // SAFETY: list keeps the exact CPython object live under the declared ABI
    // and GIL. No item storage is borrowed by this metadata snapshot.
    unsafe {
        let pointer = list.as_ptr().cast::<ffi::PyListObject>();
        Storage {
            length: (*pointer).ob_base.ob_size,
            allocated: (*pointer).allocated,
            items: (*pointer).ob_item,
        }
    }
}

#[test]
fn gc_callback_between_value_and_append_uses_current_storage() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let module = PyModule::from_code(
            py,
            c_str!(
                r#"
import gc

def mutate_on_collect(target, operation):
    calls = []
    errors = []

    def callback(phase, info):
        if phase != "start" or calls:
            return
        calls.append(phase)
        try:
            if operation == "clear":
                target.clear()
            elif operation == "grow":
                target.extend([None] * 257)
            elif operation == "shrink":
                del target[1:]
            else:
                raise AssertionError(operation)
        except BaseException as error:
            errors.append(error)

    gc.callbacks.append(callback)
    try:
        gc.collect()
    finally:
        gc.callbacks.remove(callback)
    if errors:
        raise errors[0]
    assert calls == ["start"]
"#
            ),
            c_str!("owned_list_gc_tests.py"),
            c_str!("owned_list_gc_tests"),
        )?;
        let mutate = module.getattr("mutate_on_collect")?;
        for adapter in [false, true] {
            for operation in ["clear", "grow", "shrink"] {
                let list = PyList::empty(py);
                let (first, first_finalized) = tracked(py)?;
                for _ in 0..32 {
                    list.append(first.clone_ref(py))?;
                }
                let before = storage(&list);
                let (next, next_finalized) = tracked(py)?;
                let next_pointer = next.as_ptr();
                assert_eq!(next.get_refcnt(py), 1);
                mutate.call1((&list, operation))?;
                let changed = storage(&list);
                let retained = match operation {
                    "clear" => {
                        assert_eq!(changed.length, 0);
                        assert_eq!(changed.allocated, 0);
                        assert!(changed.items.is_null());
                        0
                    }
                    "grow" => {
                        assert_eq!(changed.length, 289);
                        assert!(changed.allocated > before.allocated);
                        32
                    }
                    "shrink" => {
                        assert_eq!(changed.length, 1);
                        assert!(changed.allocated < before.allocated);
                        assert!(changed.allocated > changed.length);
                        1
                    }
                    _ => unreachable!(),
                };
                assert_eq!(first.get_refcnt(py), retained + 1);
                assert_eq!(next.get_refcnt(py), 1);
                if adapter {
                    super::append(&list, next)?;
                } else {
                    list.append(next)?;
                }
                let after = storage(&list);
                assert_eq!(after.length, changed.length + 1);
                if changed.allocated > changed.length {
                    assert_eq!(after.items, changed.items);
                    assert_eq!(after.allocated, changed.allocated);
                }
                for index in 0..retained as usize {
                    assert_eq!(list.get_item(index)?.as_ptr(), first.as_ptr());
                }
                for index in retained as usize..changed.length as usize {
                    assert!(list.get_item(index)?.is_none());
                }
                let last = list.get_item(changed.length as usize)?;
                assert_eq!(last.as_ptr(), next_pointer);
                assert_eq!(last.get_refcnt(), 2);
                drop(last);
                assert_eq!(first.get_refcnt(py), retained + 1);
                assert_eq!(first_finalized.load(Ordering::Relaxed), 0);
                assert_eq!(next_finalized.load(Ordering::Relaxed), 0);
                drop(list);
                assert_eq!(first.get_refcnt(py), 1);
                assert_eq!(next_finalized.load(Ordering::Relaxed), 1);
                drop(first);
                assert_eq!(first_finalized.load(Ordering::Relaxed), 1);
            }
        }
        Ok(())
    })
}
