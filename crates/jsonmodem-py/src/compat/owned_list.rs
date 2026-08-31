//! Transfer decoded values into existing list storage without an extra owner.

use pyo3::{prelude::*, types::PyList};

#[cfg(all(
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
mod spare;

/// Append an owned decoded value; Python still handles allocation and growth.
#[inline]
pub(super) fn append(list: &Bound<'_, PyList>, value: PyObject) -> PyResult<()> {
    #[cfg(all(
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
    {
        let pointer = list.as_ptr().cast::<pyo3::ffi::PyListObject>();
        // SAFETY: list owns a CPython list in this GIL-only ABI. Read its current
        // storage after constructing value, since that construction may run GC.
        // The initialized prefix owns exactly ob_size references; spare slots
        // do not own references and may be uninitialized. No Python operation
        // occurs while the pointer and size are read or the new slot is written.
        let appended = unsafe {
            spare::append_spare(
                (*pointer).ob_item.cast(),
                std::ptr::addr_of_mut!((*pointer).ob_base.ob_size),
                (*pointer).allocated,
                value.as_ptr().cast(),
            )
        };
        if appended {
            // into_ptr cannot fail, allocate or call Python. The slot now owns
            // this reference; do not run any operation before relinquishing it.
            let _ = value.into_ptr();
            return Ok(());
        }
    }
    list.append(value)
}

#[cfg(test)]
mod tests;
