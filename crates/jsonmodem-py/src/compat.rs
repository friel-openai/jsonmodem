//! Complete-document operations: no streaming events and no Python
//! preprocessing.

mod escape_mask;
#[cfg_attr(
    not(all(
        Py_3_12,
        not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
        not(any(py_sys_config = "Py_TRACE_REFS", py_sys_config = "Py_REF_DEBUG")),
        target_os = "linux",
        target_arch = "x86_64",
        target_pointer_width = "64",
        target_endian = "little",
    )),
    allow(dead_code)
)]
mod integer;
mod objects;

#[cfg(all(
    Py_3_12,
    not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
    not(py_sys_config = "Py_TRACE_REFS"),
    target_os = "linux",
    target_arch = "x86_64",
    target_pointer_width = "64",
    target_endian = "little",
))]
mod borrowed_dict;

use std::{borrow::Cow, collections::HashMap, ops::Range};

use integer::Integer;
use jsonmodem::document::{DocumentError, DocumentReader, IntegerToken, plain_string_prefix};
use lexical_parse_float::FromLexical;
pub use objects::_dumps_objects;
use pyo3::{
    PyTraverseError, PyVisit,
    exceptions::{PyMemoryError, PyTypeError, PyValueError},
    prelude::*,
    types::{
        PyBool, PyByteArray, PyBytes, PyDict, PyFloat, PyInt, PyList, PyMemoryView, PyString,
        PyTuple,
        iter::{BoundDictIterator, BoundListIterator, BoundTupleIterator},
    },
};
use smallvec::SmallVec;

const MAX_DECODE_DEPTH: usize = 1024;
const MAX_ENCODE_DEPTH: usize = 254;
const INDENT: i32 = 1;
const NON_STR_KEYS: i32 = 4;
const SORT_KEYS: i32 = 32;
const STRICT_INTEGER: i32 = 64;
const APPEND_NEWLINE: i32 = 1024;
const INITIAL_OUTPUT_CAPACITY: usize = 256;
const MAX_RETAINED_STRING_CAPACITY: usize = 64 * 1024;

// Keep the float parser out of the container loop's instruction footprint.
#[inline(never)]
fn parse_double(text: &str) -> Result<f64, lexical_parse_float::Error> {
    // DocumentReader already checked JSON syntax; only decimal conversion remains.
    f64::from_lexical(text.as_bytes())
}

/// Borrow text from an owned string, using inline ASCII storage on supported
/// builds.
#[inline]
fn string_text<'value>(value: &'value Bound<'_, PyString>) -> PyResult<&'value str> {
    #[cfg(all(
        Py_3_12,
        not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
        not(py_sys_config = "Py_TRACE_REFS"),
        target_os = "linux",
        target_arch = "x86_64",
        target_pointer_width = "64",
        target_endian = "little",
    ))]
    if value.is_exact_instance_of::<PyString>() {
        // SAFETY: value owns an exact CPython str while the GIL is held. In the
        // selected ABI, compact ASCII has initialized, immutable ASCII data of
        // GET_LENGTH bytes. PyO3 computes its address for that ABI, including
        // empty strings. The returned view cannot outlive the owning reference.
        unsafe {
            let pointer = value.as_ptr();
            if pyo3::ffi::PyUnicode_IS_COMPACT_ASCII(pointer) != 0 {
                if let Ok(length) = usize::try_from(pyo3::ffi::PyUnicode_GET_LENGTH(pointer)) {
                    let bytes = std::slice::from_raw_parts(
                        pyo3::ffi::PyUnicode_1BYTE_DATA(pointer),
                        length,
                    );
                    return Ok(std::str::from_utf8_unchecked(bytes));
                }
            }
        }
    }
    value.to_str()
}

/// Explicit raw output, retaining its owner without parsing or placeholder
/// substitution.
#[pyclass(module = "jsonmodem", frozen)]
pub struct Fragment {
    contents: PyObject,
}

#[pymethods]
impl Fragment {
    #[new]
    #[pyo3(signature = (contents, /))]
    fn new(contents: PyObject) -> Self {
        Self { contents }
    }

    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        visit.call(&self.contents)
    }
}

/// One document's container construction and bounded cache of repeated keys.
struct Decoder<'py, 'src> {
    py: Python<'py>,
    input: &'src str,
    reader: DocumentReader<'src>,
    // Python strings and cached escaped keys own their text before this is reused.
    string_buffer: String,
    keys: Option<HashMap<Cow<'src, str>, Py<PyString>>>,
    cache_keys: bool,
}

/// Unfinished containers use bounded inline storage, spilling to the heap
/// without recursive calls.
enum DecodeContainer<'py> {
    Array(Bound<'py, PyList>),
    Object(Bound<'py, PyDict>, Py<PyString>),
}

impl<'py, 'src> Decoder<'py, 'src> {
    #[cold]
    #[inline(never)]
    fn error(&self, error: DocumentError) -> PyErr {
        let position = match self.input.get(..error.offset) {
            Some(prefix) => prefix.chars().count(),
            // Preserve the count for offsets that split a character or exceed the input.
            None => self
                .input
                .char_indices()
                .take_while(|(i, _)| *i < error.offset)
                .count(),
        };
        super::json_decode_error(self.py, error.message, self.input, position)
    }

    fn fail(&self, message: &'static str) -> PyErr {
        self.error(self.reader.error(message))
    }

    fn expect(&mut self, byte: u8) -> PyResult<()> {
        self.reader.expect(byte).map_err(|error| self.error(error))
    }

    #[inline]
    fn release_large_string_buffer(&mut self) {
        // A large first token must not stay allocated while later containers grow.
        if self.string_buffer.capacity() > MAX_RETAINED_STRING_CAPACITY {
            self.string_buffer = String::new();
        }
    }

    fn key(&mut self) -> PyResult<Py<PyString>> {
        let borrowed = self
            .reader
            .string_with_buffer(&mut self.string_buffer)
            .map_err(|error| self.error(error))?;
        let text = borrowed.unwrap_or(&self.string_buffer);
        let key = if self.cache_keys && text.len() <= 64 {
            let keys = self.keys.get_or_insert_with(HashMap::new);
            match keys.get(text) {
                Some(key) => key.clone_ref(self.py),
                None => {
                    let key = PyString::new(self.py, text).unbind();
                    if keys.len() < 512 {
                        let text = match borrowed {
                            Some(text) => Cow::Borrowed(text),
                            None => Cow::Owned(text.to_owned()),
                        };
                        keys.insert(text, key.clone_ref(self.py));
                    }
                    key
                }
            }
        } else {
            PyString::new(self.py, text).unbind()
        };
        if borrowed.is_none() {
            self.release_large_string_buffer();
        }
        self.expect(b':')?;
        Ok(key)
    }

    fn value(&mut self) -> PyResult<PyObject> {
        let py = self.py;
        let mut stack: SmallVec<[DecodeContainer<'_>; 2]> = SmallVec::new();
        'next_value: loop {
            let mut value = match self.reader.peek() {
                Some(b'[') => {
                    if stack.len() >= MAX_DECODE_DEPTH {
                        return Err(self.fail("recursion depth exceeded"));
                    }
                    self.expect(b'[')?;
                    let list = PyList::empty(py);
                    if self.reader.peek() != Some(b']') {
                        stack.push(DecodeContainer::Array(list));
                        continue;
                    }
                    self.expect(b']')?;
                    list.into_any().unbind()
                }
                Some(b'{') => {
                    if stack.len() >= MAX_DECODE_DEPTH {
                        return Err(self.fail("recursion depth exceeded"));
                    }
                    self.expect(b'{')?;
                    let dict = PyDict::new(py);
                    if self.reader.peek() != Some(b'}') {
                        let key = self.key()?;
                        stack.push(DecodeContainer::Object(dict, key));
                        continue;
                    }
                    self.expect(b'}')?;
                    dict.into_any().unbind()
                }
                Some(b'"') => {
                    let borrowed = self
                        .reader
                        .string_with_buffer(&mut self.string_buffer)
                        .map_err(|error| self.error(error))?;
                    let value = PyString::new(py, borrowed.unwrap_or(&self.string_buffer))
                        .into_any()
                        .unbind();
                    if borrowed.is_none() {
                        self.release_large_string_buffer();
                    }
                    value
                }
                Some(b'n') => {
                    self.reader
                        .literal("null")
                        .map_err(|error| self.error(error))?;
                    py.None()
                }
                Some(b't') => {
                    self.reader
                        .literal("true")
                        .map_err(|error| self.error(error))?;
                    true.into_pyobject(py)?.to_owned().into_any().unbind()
                }
                Some(b'f') => {
                    self.reader
                        .literal("false")
                        .map_err(|error| self.error(error))?;
                    false.into_pyobject(py)?.to_owned().into_any().unbind()
                }
                Some(b'-' | b'0'..=b'9') => {
                    let number = self.reader.number().map_err(|error| self.error(error))?;
                    match number.integer {
                        Some(IntegerToken::Signed(value)) => {
                            value.into_pyobject(py)?.into_any().unbind()
                        }
                        Some(IntegerToken::Unsigned(value)) => {
                            value.into_pyobject(py)?.into_any().unbind()
                        }
                        None => {
                            let value = parse_double(number.text)
                                .map_err(|_| self.fail("invalid number"))?;
                            if !value.is_finite() {
                                return Err(self.fail("number is infinity when parsed as double"));
                            }
                            value.into_pyobject(py)?.into_any().unbind()
                        }
                    }
                }
                _ => return Err(self.fail("expected JSON value")),
            };
            loop {
                match stack.last_mut() {
                    None => return Ok(value),
                    Some(DecodeContainer::Array(list)) => {
                        list.append(value)?;
                        match self.reader.peek() {
                            Some(b',') => {
                                self.expect(b',')?;
                                continue 'next_value;
                            }
                            Some(b']') => self.expect(b']')?,
                            _ => return Err(self.fail("expected comma or closing bracket")),
                        }
                    }
                    Some(DecodeContainer::Object(dict, key)) => {
                        dict.set_item(key.bind(py), value)?;
                        match self.reader.peek() {
                            Some(b',') => {
                                self.expect(b',')?;
                                *key = self.key()?;
                                continue 'next_value;
                            }
                            Some(b'}') => self.expect(b'}')?,
                            _ => return Err(self.fail("expected comma or closing brace")),
                        }
                    }
                }
                value = match stack.pop().expect("unfinished container") {
                    DecodeContainer::Array(list) => list.into_any().unbind(),
                    DecodeContainer::Object(dict, _) => dict.into_any().unbind(),
                };
            }
        }
    }
}

fn decode(py: Python<'_>, input: &str) -> PyResult<PyObject> {
    if input.is_empty() {
        return Err(super::json_decode_error(
            py,
            "Input is a zero-length, empty document",
            input,
            0,
        ));
    }
    let mut decoder = Decoder {
        py,
        input,
        reader: DocumentReader::new(input),
        string_buffer: String::new(),
        keys: None,
        cache_keys: input.len() >= 1024,
    };
    let value = decoder.value()?;
    if decoder.reader.peek().is_some() {
        return Err(decoder.fail("unexpected content after document"));
    }
    Ok(value)
}

/// Decode complete input without incremental parsing or event objects.
#[pyfunction]
#[pyo3(signature = (input, /))]
pub fn loads(py: Python<'_>, input: Bound<'_, PyAny>) -> PyResult<PyObject> {
    if let Ok(text) = input.downcast_exact::<PyString>() {
        let text = text
            .to_str()
            .map_err(|_| super::json_decode_error(py, "str is not valid UTF-8", "", 0))?;
        return decode(py, text);
    }
    if let Ok(bytes) = input.downcast_exact::<PyBytes>() {
        return decode_bytes(py, bytes.as_bytes());
    }
    if input.is_exact_instance_of::<PyByteArray>() {
        let bytes = input.downcast::<PyByteArray>()?.to_vec();
        return decode_bytes(py, &bytes);
    }
    if input.is_exact_instance_of::<PyMemoryView>() {
        let view_error = |error: PyErr| {
            if error.is_instance_of::<PyValueError>(py) {
                super::json_decode_error(py, "memoryview has been released", "", 0)
            } else {
                error
            }
        };
        if !input
            .getattr(pyo3::intern!(py, "c_contiguous"))
            .map_err(view_error)?
            .extract::<bool>()?
        {
            return Err(super::json_decode_error(
                py,
                "memoryview must be contiguous bytes",
                "",
                0,
            ));
        }
        // CPython copies the view before Rust reads it, including read-only
        // views of mutable storage. Native providers must keep that storage valid.
        let bytes = input
            .call_method0(pyo3::intern!(py, "tobytes"))
            .map_err(view_error)?;
        return decode_bytes(py, bytes.downcast::<PyBytes>()?.as_bytes());
    }
    Err(super::json_decode_error(
        py,
        "Input must be bytes, bytearray, memoryview, or str",
        "",
        0,
    ))
}

fn decode_bytes(py: Python<'_>, bytes: &[u8]) -> PyResult<PyObject> {
    // Limit SIMD dispatch to long inputs with early non-ASCII bytes.
    if bytes.len() >= 128 && !bytes[..32].is_ascii() {
        let input = simdutf8::compat::from_utf8(bytes)
            .map_err(|_| super::json_decode_error(py, "str is not valid UTF-8", "", 0))?;
        return decode(py, input);
    }
    let input = std::str::from_utf8(bytes)
        .map_err(|_| super::json_decode_error(py, "str is not valid UTF-8", "", 0))?;
    decode(py, input)
}

/// Cached storage check. Only copy_integer may record a checked result.
#[cfg(all(
    Py_3_12,
    not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
    not(any(py_sys_config = "Py_TRACE_REFS", py_sys_config = "Py_REF_DEBUG")),
    target_os = "linux",
    target_arch = "x86_64",
    target_pointer_width = "64",
    target_endian = "little",
))]
#[repr(u8)]
enum IntegerLayout {
    Unchecked,
    Supported,
    Fallback,
}

/// Copy an owned exact integer only on the reviewed CPython layout.
#[cfg(all(
    Py_3_12,
    not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
    not(any(py_sys_config = "Py_TRACE_REFS", py_sys_config = "Py_REF_DEBUG")),
    target_os = "linux",
    target_arch = "x86_64",
    target_pointer_width = "64",
    target_endian = "little",
))]
#[inline(always)]
fn copy_integer(value: &Bound<'_, PyInt>, layout: &mut IntegerLayout) -> Option<Integer> {
    /// Excluding digits avoids a padded struct read beyond a small allocation.
    #[repr(C)]
    struct IntegerPrefix {
        _header: pyo3::ffi::PyObject,
        tag: usize,
    }

    if !value.is_exact_instance_of::<PyInt>() {
        return None;
    }
    let layout_matches = match layout {
        IntegerLayout::Unchecked => {
            let expected_offset = isize::try_from(std::mem::size_of::<IntegerPrefix>()).ok()?;
            let integer_type = std::ptr::addr_of!(pyo3::ffi::PyLong_Type);
            // SAFETY: Bound keeps Python attached to the GIL. These built-in
            // fields are the first digit's offset and sizeof(digit). The type
            // is immutable; no ordinary callback can change this cached result.
            let matches = unsafe {
                (*integer_type).tp_basicsize == expected_offset && (*integer_type).tp_itemsize == 4
            };
            *layout = if matches {
                IntegerLayout::Supported
            } else {
                IntegerLayout::Fallback
            };
            matches
        }
        IntegerLayout::Supported => true,
        IntegerLayout::Fallback => false,
    };
    let tag = value
        .as_ptr()
        .cast::<u8>()
        .wrapping_add(std::mem::offset_of!(IntegerPrefix, tag))
        .cast::<usize>();
    // SAFETY: Bound retains an exact immutable int under the GIL. The selected
    // ABI provides the initialized tag, and the cached metadata check proves
    // the following digits' offset and width. Each counted digit is initialized
    // and below 2^30. The helper reads no digit for zero or an unsupported count,
    // makes no Python call, and retains no pointer. A false layout reads nothing.
    unsafe { integer::read_integer(tag, layout_matches) }
}

/// Return a signed integer, or select unsigned conversion without an exception.
#[inline(always)]
fn signed_integer(value: &Bound<'_, PyInt>) -> PyResult<Option<i64>> {
    let mut overflow = 0;
    // SAFETY: Bound retains the integer while Python is attached, and overflow
    // is a live, initialized C int for the duration of this call.
    let integer = unsafe { pyo3::ffi::PyLong_AsLongLongAndOverflow(value.as_ptr(), &mut overflow) };
    match overflow {
        0 => {
            if integer == -1 {
                if let Some(error) = PyErr::take(value.py()) {
                    return Err(error);
                }
            }
            Ok(Some(integer))
        }
        1 => Ok(None),
        _ => Err(PyTypeError::new_err("Integer exceeds 64-bit range")),
    }
}

/// Use native-word conversion where size_t spans the unsigned 64-bit range.
#[inline(always)]
fn unsigned_integer(value: &Bound<'_, PyInt>) -> PyResult<u64> {
    #[cfg(target_pointer_width = "64")]
    {
        // SAFETY: Bound retains the integer and keeps Python attached throughout
        // the call. The public API accepts integer objects and returns no pointer.
        let integer = unsafe { pyo3::ffi::PyLong_AsSize_t(value.as_ptr()) };
        if integer == usize::MAX {
            if let Some(error) = PyErr::take(value.py()) {
                return Err(error);
            }
        }
        Ok(integer as u64)
    }
    #[cfg(not(target_pointer_width = "64"))]
    {
        value.extract()
    }
}

/// Single output buffer and bounded cache of encoded dictionary keys.
/// Callback serialization checks output growth; the callback-free encoder
/// retains its existing write operations.
struct Encoder<const CHECKED: bool = false> {
    output: Vec<u8>,
    option: i32,
    // The Python serializer may already have unfinished parent containers.
    base_depth: usize,
    // Dataclasses retain field order and check depth before counting their object.
    dataclass_root: bool,
    #[cfg(all(
        Py_3_12,
        not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
        not(any(py_sys_config = "Py_TRACE_REFS", py_sys_config = "Py_REF_DEBUG")),
        target_os = "linux",
        target_arch = "x86_64",
        target_pointer_width = "64",
        target_endian = "little",
    ))]
    integer_layout: IntegerLayout,
    // Retained owners make identity-based reuse safe for the whole call.
    keys: Vec<(Py<PyString>, Range<usize>)>,
    // In callback-free encoding, an unset identity bit rules out a cache hit.
    key_mask: u64,
}

/// Owning iterators keep each container alive without native recursion.
enum EncodeIterator<'py> {
    Dict(BoundDictIterator<'py>),
    #[cfg(all(
        Py_3_12,
        not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
        not(py_sys_config = "Py_TRACE_REFS"),
        target_os = "linux",
        target_arch = "x86_64",
        target_pointer_width = "64",
        target_endian = "little",
    ))]
    ScalarDict(borrowed_dict::DictScalarCursor<'py>),
    Sorted(std::vec::IntoIter<(Bound<'py, PyAny>, Bound<'py, PyAny>)>),
    List(BoundListIterator<'py>),
    Tuple(BoundTupleIterator<'py>),
}

impl<'py> EncodeIterator<'py> {
    /// The caller has already selected the sorted-dictionary branch, if needed.
    fn dict<const CHECKED: bool>(dict: &Bound<'py, PyDict>, dataclass_root: bool) -> Self {
        #[cfg(all(
            Py_3_12,
            not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
            not(py_sys_config = "Py_TRACE_REFS"),
            target_os = "linux",
            target_arch = "x86_64",
            target_pointer_width = "64",
            target_endian = "little",
        ))]
        if !CHECKED && !dataclass_root {
            return Self::ScalarDict(borrowed_dict::DictScalarCursor::new(dict.clone()));
        }
        let _ = dataclass_root;
        Self::Dict(dict.iter())
    }
}

/// An unfinished container, including identity for active-ancestor cycle
/// checks.
struct EncodeContainer<'py> {
    iter: EncodeIterator<'py>,
    identity: usize,
    count: usize,
    closing: u8,
}

#[cold]
fn allocation_error() -> PyErr {
    PyMemoryError::new_err("JSON serialization allocation failed")
}

/// Output writes fail only on allocation; callers construct the Python
/// exception.
struct OutputAllocationError;

impl From<OutputAllocationError> for PyErr {
    fn from(_: OutputAllocationError) -> Self {
        allocation_error()
    }
}

impl<const CHECKED: bool> Encoder<CHECKED> {
    fn into_checked(self) -> Encoder<true> {
        Encoder {
            output: self.output,
            option: self.option,
            base_depth: self.base_depth,
            dataclass_root: self.dataclass_root,
            #[cfg(all(
                Py_3_12,
                not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
                not(any(py_sys_config = "Py_TRACE_REFS", py_sys_config = "Py_REF_DEBUG")),
                target_os = "linux",
                target_arch = "x86_64",
                target_pointer_width = "64",
                target_endian = "little",
            ))]
            integer_layout: self.integer_layout,
            keys: self.keys,
            key_mask: self.key_mask,
        }
    }

    #[inline]
    fn reserve(&mut self, additional: usize) -> Result<(), OutputAllocationError> {
        if CHECKED {
            if additional > self.output.capacity() - self.output.len() {
                self.grow(additional)?;
            }
        } else {
            self.output.reserve(additional);
        }
        Ok(())
    }

    #[cold]
    fn grow(&mut self, additional: usize) -> Result<(), OutputAllocationError> {
        self.output
            .try_reserve(additional)
            .map_err(|_| OutputAllocationError)
    }

    #[inline]
    fn push(&mut self, byte: u8) -> Result<(), OutputAllocationError> {
        if CHECKED {
            self.reserve(1)?;
        }
        self.output.push(byte);
        Ok(())
    }

    #[inline]
    fn extend(&mut self, bytes: &[u8]) -> Result<(), OutputAllocationError> {
        if CHECKED {
            self.reserve(bytes.len())?;
        }
        self.output.extend_from_slice(bytes);
        Ok(())
    }

    #[inline]
    fn bytes(&self, py: Python<'_>) -> PyResult<Py<PyBytes>> {
        let output = self.output.as_slice();
        let len = pyo3::ffi::Py_ssize_t::try_from(output.len()).map_err(|_| allocation_error())?;
        // SAFETY: output retains len initialized bytes for the synchronous copy.
        // Python is attached, and the API returns a new reference or a null
        // pointer with an exception. PyO3 takes ownership or returns that error.
        let bytes = unsafe {
            Bound::from_owned_ptr_or_err(
                py,
                pyo3::ffi::PyBytes_FromStringAndSize(output.as_ptr().cast(), len),
            )
        }?;
        Ok(bytes.downcast_into::<PyBytes>()?.unbind())
    }

    #[inline(always)]
    fn key_any(&mut self, key: &Bound<'_, PyAny>) -> PyResult<bool> {
        if let Ok(key) = key.downcast_exact::<PyString>() {
            self.key(key)?;
        } else if self.option & NON_STR_KEYS != 0
            && (key.is_none()
                || key.is_exact_instance_of::<PyBool>()
                || key.is_exact_instance_of::<PyInt>()
                || key.is_exact_instance_of::<PyFloat>())
        {
            self.push(b'"')?;
            let option = self.option;
            // OPT_STRICT_INTEGER applies to values, not converted keys.
            self.option &= !STRICT_INTEGER;
            let result = self.scalar(key);
            self.option = option;
            result?;
            self.push(b'"')?;
        } else {
            return Ok(false);
        }
        Ok(true)
    }

    fn key(&mut self, key: &Bound<'_, PyString>) -> PyResult<()> {
        let cache = self.output.len() >= 1024;
        if cache
            && (CHECKED
                || self.keys.len() < 16
                || self.key_mask & key_identity_bit(key.as_ptr() as usize) != 0)
        {
            if let Some((_, encoded)) = self
                .keys
                .iter()
                .find(|(owner, _)| owner.as_ptr() == key.as_ptr())
            {
                let encoded = encoded.clone();
                if CHECKED {
                    self.reserve(encoded.len())?;
                }
                self.output.extend_from_within(encoded);
                return Ok(());
            }
        }
        let text = string_text(key).map_err(|_| PyTypeError::new_err("str is not valid UTF-8"))?;
        let start = self.output.len();
        self.string(text)?;
        if cache && self.keys.len() < 16 && text.len() <= 64 {
            if CHECKED {
                self.keys.try_reserve(1).map_err(|_| allocation_error())?;
            }
            self.keys
                .push((key.clone().unbind(), start..self.output.len()));
            if !CHECKED {
                self.key_mask |= key_identity_bit(key.as_ptr() as usize);
            }
        }
        Ok(())
    }

    fn string(&mut self, value: &str) -> Result<(), OutputAllocationError> {
        // Avoid growing again just for the closing quote of a long plain prefix.
        if value.len() >= INITIAL_OUTPUT_CAPACITY {
            self.reserve(value.len() + 2)?;
        }
        self.push(b'"')?;
        self.string_contents(value.as_bytes())?;
        self.push(b'"')
    }

    fn string_contents(&mut self, mut remaining: &[u8]) -> Result<(), OutputAllocationError> {
        while !remaining.is_empty() {
            let prefix = plain_string_prefix(remaining);
            self.extend(&remaining[..prefix])?;
            remaining = &remaining[prefix..];
            if let Some((&byte, tail)) = remaining.split_first() {
                if let Some(block) = remaining.first_chunk::<16>() {
                    let mut escapes = escape_mask::mask(block);
                    if escapes & escapes.wrapping_sub(1) != 0 {
                        let mut start = 0;
                        while escapes != 0 {
                            let index = escapes.trailing_zeros() as usize;
                            if start < index {
                                self.extend(&block[start..index])?;
                            }
                            self.escape_byte(block[index])?;
                            start = index + 1;
                            escapes &= escapes - 1;
                        }
                        if start < block.len() {
                            self.extend(&block[start..])?;
                        }
                        remaining = &remaining[block.len()..];
                        continue;
                    }
                }
                self.escape_byte(byte)?;
                remaining = tail;
            }
        }
        Ok(())
    }

    /// Write a byte already identified as a JSON escape by either scanner.
    #[inline(always)]
    fn escape_byte(&mut self, byte: u8) -> Result<(), OutputAllocationError> {
        match byte {
            b'"' => self.extend(b"\\\""),
            b'\\' => self.extend(b"\\\\"),
            b'\n' => self.extend(b"\\n"),
            b'\r' => self.extend(b"\\r"),
            b'\t' => self.extend(b"\\t"),
            8 => self.extend(b"\\b"),
            12 => self.extend(b"\\f"),
            _ => {
                const HEX: &[u8] = b"0123456789abcdef";
                self.extend(&[
                    b'\\',
                    b'u',
                    b'0',
                    b'0',
                    HEX[usize::from(byte >> 4)],
                    HEX[usize::from(byte & 15)],
                ])
            }
        }
    }

    fn newline(&mut self, depth: usize) -> Result<(), OutputAllocationError> {
        if self.option & INDENT != 0 {
            if CHECKED {
                self.reserve(1 + (depth + self.base_depth) * 2)?;
            }
            self.output.push(b'\n');
            self.output
                .resize(self.output.len() + (depth + self.base_depth) * 2, b' ');
        }
        Ok(())
    }

    #[inline(always)]
    fn integer(&mut self, value: &Bound<'_, PyInt>) -> PyResult<Integer> {
        #[cfg(all(
            Py_3_12,
            not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
            not(any(py_sys_config = "Py_TRACE_REFS", py_sys_config = "Py_REF_DEBUG")),
            target_os = "linux",
            target_arch = "x86_64",
            target_pointer_width = "64",
            target_endian = "little",
        ))]
        if let Some(integer) = copy_integer(value, &mut self.integer_layout) {
            return Ok(integer);
        }
        if let Some(integer) = signed_integer(value)? {
            Ok(Integer::Signed(integer))
        } else {
            let integer = unsigned_integer(value)
                .map_err(|_| PyTypeError::new_err("Integer exceeds 64-bit range"))?;
            Ok(Integer::Unsigned(integer))
        }
    }

    #[inline(always)]
    fn scalar(&mut self, value: &Bound<'_, PyAny>) -> PyResult<bool> {
        if value.is_none() {
            self.extend(b"null")?;
        } else if let Ok(string) = value.downcast_exact::<PyString>() {
            self.string(
                string_text(string).map_err(|_| PyTypeError::new_err("str is not valid UTF-8"))?,
            )?;
        } else if let Ok(boolean) = value.downcast_exact::<PyBool>() {
            self.extend(if boolean.is_true() { b"true" } else { b"false" })?;
        } else if let Ok(value) = value.downcast_exact::<PyInt>() {
            let mut buffer = itoa::Buffer::new();
            match self.integer(value)? {
                Integer::Signed(integer) => {
                    if self.option & STRICT_INTEGER != 0
                        && !(-9_007_199_254_740_991..=9_007_199_254_740_991).contains(&integer)
                    {
                        return Err(PyTypeError::new_err("Integer exceeds 53-bit range"));
                    }
                    self.extend(buffer.format(integer).as_bytes())?;
                }
                Integer::Unsigned(integer) => {
                    if self.option & STRICT_INTEGER != 0 && integer > 9_007_199_254_740_991 {
                        return Err(PyTypeError::new_err("Integer exceeds 53-bit range"));
                    }
                    self.extend(buffer.format(integer).as_bytes())?;
                }
            }
        } else if let Ok(float) = value.downcast_exact::<PyFloat>() {
            let number = float.value();
            if number.is_finite() {
                self.extend(zmij::Buffer::new().format_finite(number).as_bytes())?;
            } else {
                self.extend(b"null")?;
            }
        } else if let Ok(list) = value.downcast_exact::<PyList>() {
            if !list.is_empty() {
                return Ok(false);
            }
            self.extend(b"[]")?;
        } else if let Ok(tuple) = value.downcast_exact::<PyTuple>() {
            if !tuple.is_empty() {
                return Ok(false);
            }
            self.extend(b"[]")?;
        } else if value.is_exact_instance_of::<PyDict>() {
            return Ok(false);
        } else if let Ok(fragment) = value.downcast_exact::<Fragment>() {
            let fragment = fragment.get();
            let contents = fragment.contents.bind(value.py());
            if let Ok(bytes) = contents.downcast_exact::<PyBytes>() {
                self.extend(bytes.as_bytes())?;
            } else if let Ok(text) = contents.downcast_exact::<PyString>() {
                self.extend(
                    text.to_str()
                        .map_err(|_| {
                            PyTypeError::new_err("str is not valid UTF-8: surrogates not allowed")
                        })?
                        .as_bytes(),
                )?;
            } else {
                return Err(PyTypeError::new_err(
                    "orjson.Fragment's content is not of type bytes or str",
                ));
            }
        } else {
            return Ok(false);
        }
        Ok(true)
    }

    // False means the Python reference serializer owns an unsupported type.
    // No user callback can run while these native container iterators exist.
    fn value(&mut self, value: &Bound<'_, PyAny>) -> PyResult<bool> {
        if self.scalar(value)? {
            return Ok(true);
        }
        let mut stack: SmallVec<[EncodeContainer<'_>; 2]> = SmallVec::new();
        let mut current = value.clone();
        'container: loop {
            if stack.len() + self.base_depth >= MAX_ENCODE_DEPTH
                && (!self.dataclass_root || !stack.is_empty())
            {
                if current.is_exact_instance_of::<PyDict>()
                    || current.is_exact_instance_of::<PyList>()
                    || current.is_exact_instance_of::<PyTuple>()
                {
                    return Err(PyTypeError::new_err("Recursion limit reached"));
                }
                return Ok(false);
            }
            let identity = current.as_ptr() as usize;
            if stack.iter().any(|frame| frame.identity == identity) {
                return Err(PyTypeError::new_err("circular reference"));
            }
            let (iter, opening, closing) = if let Ok(dict) = current.downcast_exact::<PyDict>() {
                if self.option & SORT_KEYS != 0 && (!self.dataclass_root || !stack.is_empty()) {
                    let mut items: Vec<_> = dict.iter().collect();
                    for (key, _) in &items {
                        let Ok(key) = key.downcast_exact::<PyString>() else {
                            return Ok(false);
                        };
                        key.to_str()
                            .map_err(|_| PyTypeError::new_err("str is not valid UTF-8"))?;
                    }
                    items.sort_unstable_by(|(left, _), (right, _)| {
                        left.downcast::<PyString>()
                            .unwrap()
                            .to_str()
                            .unwrap()
                            .cmp(right.downcast::<PyString>().unwrap().to_str().unwrap())
                    });
                    (EncodeIterator::Sorted(items.into_iter()), b'{', b'}')
                } else {
                    (
                        EncodeIterator::dict::<CHECKED>(dict, self.dataclass_root),
                        b'{',
                        b'}',
                    )
                }
            } else if let Ok(list) = current.downcast_exact::<PyList>() {
                (EncodeIterator::List(list.iter()), b'[', b']')
            } else if let Ok(tuple) = current.downcast_exact::<PyTuple>() {
                (EncodeIterator::Tuple(tuple.iter()), b'[', b']')
            } else {
                return Ok(false);
            };
            self.push(opening)?;
            stack.push(EncodeContainer {
                iter,
                identity,
                count: 0,
                closing,
            });
            loop {
                let depth = stack.len();
                let Some(frame) = stack.last_mut() else {
                    return Ok(true);
                };
                if let EncodeIterator::List(iter) = &mut frame.iter {
                    for item in iter.by_ref() {
                        if frame.count != 0 {
                            self.push(b',')?;
                        }
                        frame.count += 1;
                        self.newline(depth)?;
                        if !self.scalar(&item)? {
                            current = item;
                            continue 'container;
                        }
                    }
                    let frame = stack.pop().expect("unfinished list");
                    if frame.count != 0 {
                        self.newline(stack.len())?;
                    }
                    self.push(frame.closing)?;
                    continue;
                }
                let item = match &mut frame.iter {
                    EncodeIterator::Dict(iter) => iter.next().map(|(key, item)| (Some(key), item)),
                    #[cfg(all(
                        Py_3_12,
                        not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
                        not(py_sys_config = "Py_TRACE_REFS"),
                        target_os = "linux",
                        target_arch = "x86_64",
                        target_pointer_width = "64",
                        target_endian = "little",
                    ))]
                    EncodeIterator::ScalarDict(iter) => {
                        match iter.next(self, &mut frame.count, depth)? {
                            borrowed_dict::DictStep::Written => continue,
                            borrowed_dict::DictStep::Owned(key, item) => Some((Some(key), item)),
                            borrowed_dict::DictStep::End => None,
                        }
                    }
                    EncodeIterator::Sorted(iter) => {
                        iter.next().map(|(key, item)| (Some(key), item))
                    }
                    EncodeIterator::List(iter) => iter.next().map(|item| (None, item)),
                    EncodeIterator::Tuple(iter) => iter.next().map(|item| (None, item)),
                };
                if let Some((key, item)) = item {
                    if frame.count != 0 {
                        self.push(b',')?;
                    }
                    frame.count += 1;
                    self.newline(depth)?;
                    if let Some(key) = key {
                        if !self.key_any(&key)? {
                            return Ok(false);
                        }
                        self.push(b':')?;
                        if self.option & INDENT != 0 {
                            self.push(b' ')?;
                        }
                    }
                    if !self.scalar(&item)? {
                        current = item;
                        continue 'container;
                    }
                } else {
                    let frame = stack.pop().expect("unfinished container");
                    if frame.count != 0 {
                        self.newline(stack.len())?;
                    }
                    self.push(frame.closing)?;
                }
            }
        }
    }
}

#[inline]
fn key_identity_bit(identity: usize) -> u64 {
    1 << (((identity >> 4) ^ (identity >> 10)) & 63)
}

fn supplied_default<'py>(value: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    // Explicit None is an invalid callback; an omitted argument has no callback
    // cause.
    Ok(Some(value.clone()))
}

/// Write long plain strings into Python's initialized bytes storage directly.
#[inline(never)]
fn dump_long_string(py: Python<'_>, text: &str, flags: i32) -> PyResult<PyObject> {
    let bytes = text.as_bytes();
    let prefix = plain_string_prefix(bytes);
    if prefix == bytes.len() {
        let newline = usize::from(flags & APPEND_NEWLINE != 0);
        return Ok(PyBytes::new_with(py, bytes.len() + 2 + newline, |output| {
            output[0] = b'"';
            output[1..bytes.len() + 1].copy_from_slice(bytes);
            output[bytes.len() + 1] = b'"';
            if newline != 0 {
                output[bytes.len() + 2] = b'\n';
            }
            Ok(())
        })?
        .into_any()
        .unbind());
    }
    let mut encoder = Encoder::<false> {
        output: Vec::with_capacity(bytes.len() + 2),
        option: flags,
        base_depth: 0,
        dataclass_root: false,
        #[cfg(all(
            Py_3_12,
            not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
            not(any(py_sys_config = "Py_TRACE_REFS", py_sys_config = "Py_REF_DEBUG")),
            target_os = "linux",
            target_arch = "x86_64",
            target_pointer_width = "64",
            target_endian = "little",
        ))]
        integer_layout: IntegerLayout::Unchecked,
        keys: Vec::new(),
        key_mask: 0,
    };
    encoder.output.push(b'"');
    for chunk in bytes[..prefix].chunks(1024) {
        encoder.output.extend_from_slice(chunk);
    }
    encoder.string_contents(&bytes[prefix..])?;
    encoder.output.push(b'"');
    if flags & APPEND_NEWLINE != 0 {
        encoder.output.push(b'\n');
    }
    Ok(PyBytes::new(py, &encoder.output).into_any().unbind())
}

/// Serialize common JSON types directly, preserving the uncommon-type fallback.
#[pyfunction]
#[pyo3(signature=(obj, /, default=None, option=None))]
pub fn dumps(
    py: Python<'_>,
    obj: Bound<'_, PyAny>,
    #[pyo3(from_py_with = supplied_default)] default: Option<Bound<'_, PyAny>>,
    option: Option<Bound<'_, PyAny>>,
) -> PyResult<PyObject> {
    let flags = match &option {
        None => 0,
        Some(value) if value.is_none() => 0,
        Some(value) if value.is_exact_instance_of::<PyInt>() => value
            .extract::<i32>()
            .map_err(|_| PyTypeError::new_err("unsupported option bits"))?,
        _ => return Err(PyTypeError::new_err("option must be an integer")),
    };
    if flags < 0 || flags & !4095 != 0 {
        return Err(PyTypeError::new_err("unsupported option bits"));
    }
    let root_string = if let Ok(string) = obj.downcast_exact::<PyString>() {
        let text =
            string_text(string).map_err(|_| PyTypeError::new_err("str is not valid UTF-8"))?;
        if text.len() >= INITIAL_OUTPUT_CAPACITY {
            return dump_long_string(py, text, flags);
        }
        Some(text)
    } else {
        None
    };
    let mut encoder = Encoder::<false> {
        output: Vec::with_capacity(INITIAL_OUTPUT_CAPACITY),
        option: flags,
        base_depth: 0,
        dataclass_root: false,
        #[cfg(all(
            Py_3_12,
            not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
            not(any(py_sys_config = "Py_TRACE_REFS", py_sys_config = "Py_REF_DEBUG")),
            target_os = "linux",
            target_arch = "x86_64",
            target_pointer_width = "64",
            target_endian = "little",
        ))]
        integer_layout: IntegerLayout::Unchecked,
        keys: Vec::new(),
        key_mask: 0,
    };
    let encoded = if let Some(text) = root_string {
        encoder.string(text)?;
        true
    } else {
        encoder.value(&obj)?
    };
    if encoded {
        if flags & APPEND_NEWLINE != 0 {
            encoder.push(b'\n')?;
        }
        return Ok(PyBytes::new(py, &encoder.output).into_any().unbind());
    }
    objects::dumps(py, encoder, obj, default)
}

/// Try an owning dataclass field snapshot without invoking any user callback.
#[pyfunction]
pub fn _dumps_fields(
    py: Python<'_>,
    fields: Bound<'_, PyDict>,
    option: i32,
    depth: usize,
) -> PyResult<Option<Py<PyBytes>>> {
    if depth > MAX_ENCODE_DEPTH {
        return Err(PyTypeError::new_err("Recursion limit reached"));
    }
    let mut encoder = Encoder::<false> {
        output: Vec::with_capacity(INITIAL_OUTPUT_CAPACITY),
        option,
        base_depth: depth,
        dataclass_root: true,
        #[cfg(all(
            Py_3_12,
            not(any(Py_3_14, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
            not(any(py_sys_config = "Py_TRACE_REFS", py_sys_config = "Py_REF_DEBUG")),
            target_os = "linux",
            target_arch = "x86_64",
            target_pointer_width = "64",
            target_endian = "little",
        ))]
        integer_layout: IntegerLayout::Unchecked,
        keys: Vec::new(),
        key_mask: 0,
    };
    if encoder.value(fields.as_any())? {
        Ok(Some(PyBytes::new(py, &encoder.output).unbind()))
    } else {
        Ok(None)
    }
}
