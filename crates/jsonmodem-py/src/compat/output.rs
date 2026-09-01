//! Output storage stays private until the serializer publishes complete bytes.

use std::ops::Range;

use pyo3::{prelude::*, types::PyBytes};

use super::{OutputAllocationError, allocation_error};

mod sealed {
    pub trait Sealed {}
}

/// The scalar dictionary cursor may use only writers with Rust allocation.
/// Sealing keeps its allocation assertion limited to the two implementations
/// here.
pub(super) trait OutputBuffer: sealed::Sealed + Sized {
    // Some interpreter configurations do not compile the scalar dict cursor.
    #[allow(dead_code)]
    const PYTHON_ALLOCATION: bool;

    fn len(&self) -> usize;
    fn reserve<const CHECKED: bool>(
        &mut self,
        additional: usize,
    ) -> Result<(), OutputAllocationError>;
    fn push<const CHECKED: bool>(&mut self, byte: u8) -> Result<(), OutputAllocationError>;
    fn extend<const CHECKED: bool>(&mut self, bytes: &[u8]) -> Result<(), OutputAllocationError>;
    fn duplicate<const CHECKED: bool>(
        &mut self,
        range: Range<usize>,
    ) -> Result<(), OutputAllocationError>;
    fn repeat<const CHECKED: bool>(
        &mut self,
        count: usize,
        byte: u8,
    ) -> Result<(), OutputAllocationError>;
    fn finish(self, py: Python<'_>) -> PyResult<Py<PyBytes>>;
}

impl sealed::Sealed for Vec<u8> {}

impl OutputBuffer for Vec<u8> {
    const PYTHON_ALLOCATION: bool = false;

    #[inline]
    fn len(&self) -> usize {
        self.len()
    }

    #[inline]
    fn reserve<const CHECKED: bool>(
        &mut self,
        additional: usize,
    ) -> Result<(), OutputAllocationError> {
        if CHECKED {
            self.try_reserve(additional)
                .map_err(|_| OutputAllocationError)
        } else {
            self.reserve(additional);
            Ok(())
        }
    }

    #[inline]
    fn push<const CHECKED: bool>(&mut self, byte: u8) -> Result<(), OutputAllocationError> {
        if CHECKED {
            OutputBuffer::reserve::<true>(self, 1)?;
        }
        self.push(byte);
        Ok(())
    }

    #[inline]
    fn extend<const CHECKED: bool>(&mut self, bytes: &[u8]) -> Result<(), OutputAllocationError> {
        if CHECKED {
            OutputBuffer::reserve::<true>(self, bytes.len())?;
        }
        self.extend_from_slice(bytes);
        Ok(())
    }

    #[inline]
    fn duplicate<const CHECKED: bool>(
        &mut self,
        range: Range<usize>,
    ) -> Result<(), OutputAllocationError> {
        if CHECKED {
            OutputBuffer::reserve::<true>(self, range.len())?;
        }
        self.extend_from_within(range);
        Ok(())
    }

    #[inline]
    fn repeat<const CHECKED: bool>(
        &mut self,
        count: usize,
        byte: u8,
    ) -> Result<(), OutputAllocationError> {
        if CHECKED {
            OutputBuffer::reserve::<true>(self, count)?;
        }
        self.resize(self.len() + count, byte);
        Ok(())
    }

    fn finish(self, py: Python<'_>) -> PyResult<Py<PyBytes>> {
        let len = pyo3::ffi::Py_ssize_t::try_from(self.len()).map_err(|_| allocation_error())?;
        // SAFETY: self retains len initialized bytes throughout the synchronous
        // copy. Python is attached; PyO3 receives a new reference or the error.
        let object = unsafe {
            Bound::from_owned_ptr_or_err(
                py,
                pyo3::ffi::PyBytes_FromStringAndSize(self.as_ptr().cast(), len),
            )
        }?;
        Ok(object.downcast_into::<PyBytes>()?.unbind())
    }
}

#[cfg(all(
    Py_3_12,
    not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
    not(py_sys_config = "Py_TRACE_REFS")
))]
pub(super) use python::PythonOutput as Output;

#[cfg(not(all(
    Py_3_12,
    not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
    not(py_sys_config = "Py_TRACE_REFS")
)))]
pub(super) type Output<'py> = Vec<u8>;

pub(super) fn new(py: Python<'_>, capacity: usize) -> Result<Output<'_>, OutputAllocationError> {
    #[cfg(all(
        Py_3_12,
        not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
        not(py_sys_config = "Py_TRACE_REFS")
    ))]
    {
        Output::new(py, capacity)
    }
    #[cfg(not(all(
        Py_3_12,
        not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
        not(py_sys_config = "Py_TRACE_REFS")
    )))]
    {
        let _ = py;
        let mut output = Vec::new();
        OutputBuffer::reserve::<true>(&mut output, capacity)?;
        Ok(output)
    }
}

/// Retain initialized bytes when converting the callback-aware writer.
pub(super) fn from_vec(
    py: Python<'_>,
    buffer: Vec<u8>,
) -> Result<Output<'_>, OutputAllocationError> {
    #[cfg(all(
        Py_3_12,
        not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
        not(py_sys_config = "Py_TRACE_REFS")
    ))]
    {
        Ok(Output::from_vec(py, buffer))
    }
    #[cfg(not(all(
        Py_3_12,
        not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
        not(py_sys_config = "Py_TRACE_REFS")
    )))]
    {
        let _ = py;
        Ok(buffer)
    }
}

#[cfg(all(
    Py_3_12,
    not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
    not(py_sys_config = "Py_TRACE_REFS")
))]
mod python {
    use std::{ops::Range, ptr};

    use pyo3::{ffi, prelude::*, types::PyBytes};

    use super::{OutputAllocationError, OutputBuffer};

    // _PyBytes_Resize adds the object header without checking for overflow.
    // sizeof includes at least the header, terminating byte, and any padding.
    const MAX_CAPACITY: usize = isize::MAX as usize - std::mem::size_of::<ffi::PyBytesObject>();
    const SMALL_CAPACITY: usize = 256;

    /// Keeps small output in a Vec, then owns unpublished Python bytes on
    /// growth.
    ///
    /// Both allocations use the same initialized prefix 0..len. No reference,
    /// pointer, or slice escapes while writes are possible. For Python bytes,
    /// the object's size remains capacity until finish. The attachment token
    /// keeps allocation and Drop on the owning thread.
    pub struct PythonOutput<'py> {
        py: Python<'py>,
        // Non-null selects Python storage; small is then empty.
        object: *mut ffi::PyObject,
        // The Vec's length can trail len because append operations write through
        // data. Only take_vec publishes the initialized prefix back to the Vec.
        small: Vec<u8>,
        data: *mut u8,
        len: usize,
        // Writable capacity may be smaller than small.capacity(). A restarted
        // traversal can reuse a large Vec, but should still promote on growth.
        capacity: usize,
    }

    impl<'py> PythonOutput<'py> {
        pub(super) fn new(py: Python<'py>, capacity: usize) -> Result<Self, OutputAllocationError> {
            let mut buffer = Vec::new();
            buffer
                .try_reserve_exact(capacity)
                .map_err(|_| OutputAllocationError)?;
            Ok(Self::from_vec(py, buffer))
        }

        pub(super) fn from_vec(py: Python<'py>, mut buffer: Vec<u8>) -> Self {
            Self {
                py,
                object: ptr::null_mut(),
                data: buffer.as_mut_ptr(),
                len: buffer.len(),
                capacity: buffer.capacity().min(SMALL_CAPACITY).max(buffer.len()),
                small: buffer,
            }
        }

        fn take_vec(&mut self) -> Vec<u8> {
            assert!(self.object.is_null());
            // SAFETY: every append initializes bytes before advancing len, and
            // writable capacity never exceeds the Vec's allocated capacity.
            // No view of the allocation is exposed while this owner can write.
            unsafe { self.small.set_len(self.len) };
            self.data = ptr::null_mut();
            self.len = 0;
            self.capacity = 0;
            std::mem::take(&mut self.small)
        }

        #[cold]
        fn grow(&mut self, additional: usize) -> Result<(), OutputAllocationError> {
            let required = self
                .len
                .checked_add(additional)
                .ok_or(OutputAllocationError)?;
            let capacity = required
                .max(self.capacity.saturating_mul(2))
                .max(self.small.capacity())
                .max(8);
            if capacity > MAX_CAPACITY {
                return Err(OutputAllocationError);
            }
            if self.object.is_null() {
                if self.len <= SMALL_CAPACITY {
                    let buffer = self.take_vec();
                    let mut prefix = [0; SMALL_CAPACITY];
                    let len = buffer.len();
                    prefix[..len].copy_from_slice(&buffer);
                    // A restart may bring a large allocation. Release it before
                    // allocating Python bytes, not after the output is copied.
                    drop(buffer);
                    self.allocate(capacity)?;
                    self.extend::<true>(&prefix[..len])
                } else {
                    // Nonempty conversion can bring more than SMALL_CAPACITY
                    // bytes. Keep those bytes owned until the copy completes.
                    let prefix = self.take_vec();
                    self.allocate(capacity)?;
                    self.extend::<true>(&prefix)
                }
            } else {
                self.resize(capacity)
            }
        }

        fn allocate(&mut self, capacity: usize) -> Result<(), OutputAllocationError> {
            assert!(self.object.is_null() && self.small.capacity() == 0);
            assert!(capacity > 0 && capacity <= MAX_CAPACITY);
            // SAFETY: capacity includes room for CPython's header in Py_ssize_t.
            // A null source requests writable storage. A positive size avoids
            // the shared empty-bytes singleton. Python is attached.
            self.object =
                unsafe { ffi::PyBytes_FromStringAndSize(ptr::null(), capacity as ffi::Py_ssize_t) };
            if self.object.is_null() {
                drop(PyErr::fetch(self.py));
                return Err(OutputAllocationError);
            }
            self.refresh(capacity);
            Ok(())
        }

        fn resize(&mut self, capacity: usize) -> Result<(), OutputAllocationError> {
            assert!(!self.object.is_null());
            assert!(capacity > 0 && capacity >= self.len && capacity <= MAX_CAPACITY);
            // SAFETY: object is uniquely owned, exact, and unpublished. Python
            // is attached. No borrowed view survives this call. The API replaces
            // our owned pointer and frees/nulls it on failure; it sets the final
            // null byte on success, including when shrinking for publication.
            if unsafe { ffi::_PyBytes_Resize(&mut self.object, capacity as ffi::Py_ssize_t) } != 0 {
                self.data = ptr::null_mut();
                self.len = 0;
                self.capacity = 0;
                drop(PyErr::fetch(self.py));
                return Err(OutputAllocationError);
            }
            self.refresh(capacity);
            Ok(())
        }

        fn refresh(&mut self, capacity: usize) {
            // SAFETY: the preceding successful allocation or resize leaves a
            // live exact bytes object. The API returns its writable storage.
            self.data = unsafe { ffi::PyBytes_AsString(self.object) }.cast();
            assert!(!self.data.is_null());
            self.capacity = capacity;
        }
    }

    impl super::sealed::Sealed for PythonOutput<'_> {}

    impl OutputBuffer for PythonOutput<'_> {
        const PYTHON_ALLOCATION: bool = true;

        #[inline]
        fn len(&self) -> usize {
            self.len
        }

        #[inline]
        fn reserve<const CHECKED: bool>(
            &mut self,
            additional: usize,
        ) -> Result<(), OutputAllocationError> {
            if additional > self.capacity - self.len {
                self.grow(additional)?;
            }
            Ok(())
        }

        #[inline]
        fn push<const CHECKED: bool>(&mut self, byte: u8) -> Result<(), OutputAllocationError> {
            self.reserve::<true>(1)?;
            // SAFETY: reserve established len < capacity in our private storage.
            unsafe { self.data.add(self.len).write(byte) };
            self.len += 1;
            Ok(())
        }

        #[inline]
        fn extend<const CHECKED: bool>(
            &mut self,
            bytes: &[u8],
        ) -> Result<(), OutputAllocationError> {
            if bytes.is_empty() {
                return Ok(());
            }
            self.reserve::<true>(bytes.len())?;
            // SAFETY: reserve established enough private writable storage. This
            // type never exposes its allocation, so bytes cannot alias it.
            unsafe {
                ptr::copy_nonoverlapping(bytes.as_ptr(), self.data.add(self.len), bytes.len());
            }
            self.len += bytes.len();
            Ok(())
        }

        #[inline]
        fn duplicate<const CHECKED: bool>(
            &mut self,
            range: Range<usize>,
        ) -> Result<(), OutputAllocationError> {
            assert!(range.start <= range.end && range.end <= self.len);
            if range.is_empty() {
                return Ok(());
            }
            self.reserve::<true>(range.len())?;
            // SAFETY: range refers only to initialized bytes before the old len.
            // The appended destination cannot overlap it. Both pointers use the
            // current allocation, after reserve has finished any relocation.
            unsafe {
                ptr::copy_nonoverlapping(
                    self.data.add(range.start),
                    self.data.add(self.len),
                    range.len(),
                );
            }
            self.len += range.len();
            Ok(())
        }

        #[inline]
        fn repeat<const CHECKED: bool>(
            &mut self,
            count: usize,
            byte: u8,
        ) -> Result<(), OutputAllocationError> {
            if count == 0 {
                return Ok(());
            }
            self.reserve::<true>(count)?;
            // SAFETY: reserve established count writable bytes after len.
            unsafe { ptr::write_bytes(self.data.add(self.len), byte, count) };
            self.len += count;
            Ok(())
        }

        fn finish(mut self, _: Python<'_>) -> PyResult<Py<PyBytes>> {
            if self.object.is_null() {
                return self.take_vec().finish(self.py);
            }
            if self.len == 0 {
                return Ok(PyBytes::new(self.py, b"").unbind());
            }
            if self.len != self.capacity {
                self.resize(self.len)?;
            }
            let object = std::mem::replace(&mut self.object, ptr::null_mut());
            // SAFETY: all len bytes are initialized and CPython has set both
            // the length and terminator. Ownership moves to PyO3 exactly once;
            // no further write is possible because finish consumes self.
            Ok(unsafe { Py::from_owned_ptr(self.py, object) })
        }
    }

    impl Drop for PythonOutput<'_> {
        fn drop(&mut self) {
            // SAFETY: the attachment token is live. A non-null pointer is the
            // unique owned bytes reference; failed resize and finish null it.
            // Exact bytes destruction does not inspect uninitialized contents.
            unsafe { ffi::Py_XDECREF(self.object) };
        }
    }

    #[cfg(test)]
    mod tests {
        use pyo3::{prelude::*, types::PyBytesMethods};

        use super::{OutputBuffer, PythonOutput, SMALL_CAPACITY};

        #[test]
        fn small_output_reuses_vec_until_promotion() -> PyResult<()> {
            pyo3::prepare_freethreaded_python();
            Python::with_gil(|py| {
                let mut buffer = Vec::with_capacity(4096);
                let data = buffer.as_mut_ptr();
                let mut output = PythonOutput::from_vec(py, buffer);
                output.repeat::<true>(SMALL_CAPACITY / 2, b'x')?;
                output.duplicate::<true>(0..SMALL_CAPACITY / 2)?;
                assert!(output.object.is_null());
                assert_eq!(output.data, data);
                output.duplicate::<true>(0..1)?;
                assert!(!output.object.is_null());
                assert_eq!(output.small.capacity(), 0);
                assert_eq!(output.capacity, 4096);
                let result = output.finish(py)?;
                assert_eq!(result.bind(py).as_bytes(), vec![b'x'; SMALL_CAPACITY + 1]);
                Ok(())
            })
        }

        #[test]
        fn large_nonempty_vec_survives_promotion() -> PyResult<()> {
            pyo3::prepare_freethreaded_python();
            Python::with_gil(|py| {
                let mut expected = vec![b'x'; SMALL_CAPACITY + 1];
                let mut output = PythonOutput::from_vec(py, expected.clone());
                output.duplicate::<true>(0..SMALL_CAPACITY)?;
                expected.extend_from_within(0..SMALL_CAPACITY);
                assert!(!output.object.is_null());
                assert!(output.reserve::<true>(usize::MAX).is_err());
                let result = output.finish(py)?;
                assert_eq!(result.bind(py).as_bytes(), expected);
                Ok(())
            })
        }
    }
}

#[cfg(test)]
mod tests {
    use pyo3::{prelude::*, types::PyBytesMethods};

    use super::{OutputBuffer, from_vec, new};

    #[test]
    fn converting_vec_preserves_cached_output_ranges() -> PyResult<()> {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let mut buffer = Vec::with_capacity(1024);
            buffer.extend_from_slice(b"first,second,");
            let mut output = from_vec(py, buffer)?;
            output.duplicate::<true>(6..12)?;
            let bytes = output.finish(py)?;
            assert_eq!(bytes.bind(py).as_bytes(), b"first,second,second");
            Ok(())
        })
    }

    #[test]
    fn growth_and_duplicates_preserve_initialized_bytes() -> PyResult<()> {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let mut output = new(py, 1)?;
            let mut expected = Vec::new();
            for index in 0..2000 {
                let bytes = index.to_string();
                output.extend::<true>(bytes.as_bytes())?;
                expected.extend_from_slice(bytes.as_bytes());
                output.push::<true>(b',')?;
                expected.push(b',');
                if index % 7 == 6 {
                    output.duplicate::<true>(0..4)?;
                    expected.extend_from_within(0..4);
                }
            }
            let bytes = output.finish(py)?;
            assert_eq!(bytes.bind(py).as_bytes(), expected);
            Ok(())
        })
    }

    #[test]
    fn padding_initializes_only_the_published_contents() -> PyResult<()> {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let mut output = new(py, 4096)?;
            output.extend::<true>(b"[\n")?;
            output.repeat::<true>(2, b' ')?;
            output.extend::<true>(b"null\n]")?;
            let bytes = output.finish(py)?;
            assert_eq!(bytes.bind(py).as_bytes(), b"[\n  null\n]");
            Ok(())
        })
    }

    #[test]
    fn impossible_reservation_leaves_current_contents_owned() -> PyResult<()> {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let mut output = new(py, 8)?;
            output.extend::<true>(b"current")?;
            assert!(output.reserve::<true>(usize::MAX).is_err());
            let bytes = output.finish(py)?;
            assert_eq!(bytes.bind(py).as_bytes(), b"current");
            Ok(())
        })
    }

    #[test]
    fn empty_and_single_byte_results_are_finished_before_publication() -> PyResult<()> {
        pyo3::prepare_freethreaded_python();
        Python::with_gil(|py| {
            let empty = new(py, 0)?.finish(py)?;
            let reserved = new(py, 256)?.finish(py)?;
            let mut output = new(py, 1)?;
            output.push::<true>(b'7')?;
            let single = output.finish(py)?;
            assert_eq!(empty.bind(py).as_bytes(), b"");
            assert_eq!(reserved.bind(py).as_bytes(), b"");
            assert_eq!(single.bind(py).as_bytes(), b"7");
            Ok(())
        })
    }
}
