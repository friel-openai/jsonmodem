//! Complete-document operations: no streaming events and no Python
//! preprocessing.

use std::{borrow::Cow, collections::HashMap, ops::Range};

use jsonmodem::document::{DocumentError, DocumentReader, plain_string_prefix};
use pyo3::{
    PyTraverseError, PyVisit,
    exceptions::PyTypeError,
    prelude::*,
    types::{
        PyBool, PyByteArray, PyBytes, PyDict, PyFloat, PyInt, PyList, PyMemoryView, PyString,
        PyTuple,
        iter::{BoundDictIterator, BoundListIterator, BoundTupleIterator},
    },
};

const MAX_DECODE_DEPTH: usize = 1024;
const MAX_ENCODE_DEPTH: usize = 254;
const INDENT: i32 = 1;
const NON_STR_KEYS: i32 = 4;
const SORT_KEYS: i32 = 32;
const STRICT_INTEGER: i32 = 64;
const APPEND_NEWLINE: i32 = 1024;

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
    keys: HashMap<Cow<'src, str>, Py<PyString>>,
    cache_keys: bool,
}

/// Unfinished containers live on the heap, independent of Python thread stack
/// size.
enum DecodeContainer<'py> {
    Array(Bound<'py, PyList>),
    Object(Bound<'py, PyDict>, Py<PyString>),
}

impl<'py, 'src> Decoder<'py, 'src> {
    fn error(&self, error: DocumentError) -> PyErr {
        let position = self
            .input
            .char_indices()
            .take_while(|(i, _)| *i < error.offset)
            .count();
        super::json_decode_error(self.py, error.message, self.input, position)
    }

    fn fail(&self, message: &'static str) -> PyErr {
        self.error(self.reader.error(message))
    }

    fn expect(&mut self, byte: u8) -> PyResult<()> {
        self.reader.expect(byte).map_err(|error| self.error(error))
    }

    fn key(&mut self) -> PyResult<Py<PyString>> {
        let text = self.reader.string().map_err(|error| self.error(error))?;
        let key = if self.cache_keys {
            match self.keys.get(text.as_ref()) {
                Some(key) => key.clone_ref(self.py),
                None => {
                    let key = PyString::new(self.py, &text).unbind();
                    if self.keys.len() < 512 && text.len() <= 64 {
                        self.keys.insert(text, key.clone_ref(self.py));
                    }
                    key
                }
            }
        } else {
            PyString::new(self.py, &text).unbind()
        };
        self.expect(b':')?;
        Ok(key)
    }

    fn value(&mut self) -> PyResult<PyObject> {
        let py = self.py;
        let mut stack = Vec::new();
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
                    let text = self.reader.string().map_err(|error| self.error(error))?;
                    PyString::new(py, &text).into_any().unbind()
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
                    if number.is_float {
                        let value: f64 = number
                            .text
                            .parse()
                            .map_err(|_| self.fail("invalid number"))?;
                        if !value.is_finite() {
                            return Err(self.fail("number is infinity when parsed as double"));
                        }
                        value.into_pyobject(py)?.into_any().unbind()
                    } else if let Ok(value) = number.text.parse::<i64>() {
                        value.into_pyobject(py)?.into_any().unbind()
                    } else if let Ok(value) = number.text.parse::<u64>() {
                        value.into_pyobject(py)?.into_any().unbind()
                    } else {
                        let value = number
                            .text
                            .parse::<f64>()
                            .map_err(|_| self.fail("invalid number"))?;
                        if !value.is_finite() {
                            return Err(self.fail("number is infinity when parsed as double"));
                        }
                        value.into_pyobject(py)?.into_any().unbind()
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
        keys: HashMap::new(),
        cache_keys: input.len() >= 1024,
    };
    let value = decoder.value()?;
    if decoder.reader.peek().is_some() {
        return Err(decoder.fail("trailing content"));
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
    // Only built-in owners are accepted. Never borrow a Rust slice from an
    // arbitrary exporter's pointer, even through a read-only memoryview.
    if input.is_exact_instance_of::<PyByteArray>() {
        let bytes = input.downcast::<PyByteArray>()?.to_vec();
        return decode_bytes(py, &bytes);
    }
    if input.is_exact_instance_of::<PyMemoryView>() {
        let owner = input.getattr("obj")?;
        if !owner.is_exact_instance_of::<PyBytes>() && !owner.is_exact_instance_of::<PyByteArray>()
        {
            // BytesIO exports an internal built-in owner, not the BytesIO object itself.
            let builtin = py
                .import("_io")?
                .getattr("BytesIO")?
                .call0()?
                .call_method0("getbuffer")?
                .getattr("obj")?;
            if !owner.get_type().is(builtin.get_type()) {
                return Err(super::json_decode_error(
                    py,
                    "memoryview must have a supported built-in owner",
                    "",
                    0,
                ));
            }
        }
        if !input.getattr("c_contiguous")?.extract::<bool>()? {
            return Err(super::json_decode_error(
                py,
                "memoryview must be contiguous bytes",
                "",
                0,
            ));
        }
        let bytes = input.call_method0("tobytes")?;
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
    let input = std::str::from_utf8(bytes)
        .map_err(|_| super::json_decode_error(py, "str is not valid UTF-8", "", 0))?;
    decode(py, input)
}

/// Single output buffer and bounded cache of encoded dictionary keys.
struct Encoder {
    output: Vec<u8>,
    option: i32,
    // The Python serializer may already have unfinished parent containers.
    base_depth: usize,
    // Dataclasses retain field order and check depth before counting their object.
    dataclass_root: bool,
    // Retained owners make identity-based reuse safe for the whole call.
    keys: Vec<(Py<PyString>, Range<usize>)>,
}

/// Owning iterators keep each container alive without native recursion.
enum EncodeIterator<'py> {
    Dict(BoundDictIterator<'py>),
    Sorted(std::vec::IntoIter<(Bound<'py, PyAny>, Bound<'py, PyAny>)>),
    List(BoundListIterator<'py>),
    Tuple(BoundTupleIterator<'py>),
}

/// An unfinished container, including identity for active-ancestor cycle
/// checks.
struct EncodeContainer<'py> {
    iter: EncodeIterator<'py>,
    identity: usize,
    count: usize,
    closing: u8,
}

impl Encoder {
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
            self.output.push(b'"');
            let option = self.option;
            // OPT_STRICT_INTEGER applies to values, not converted keys.
            self.option &= !STRICT_INTEGER;
            let result = self.scalar(key);
            self.option = option;
            result?;
            self.output.push(b'"');
        } else {
            return Ok(false);
        }
        Ok(true)
    }

    fn key(&mut self, key: &Bound<'_, PyString>) -> PyResult<()> {
        let cache = self.output.len() >= 1024;
        if cache {
            if let Some((_, encoded)) = self
                .keys
                .iter()
                .find(|(owner, _)| owner.as_ptr() == key.as_ptr())
            {
                self.output.extend_from_within(encoded.clone());
                return Ok(());
            }
        }
        let text = key
            .to_str()
            .map_err(|_| PyTypeError::new_err("str is not valid UTF-8"))?;
        let start = self.output.len();
        self.string(text);
        if cache && self.keys.len() < 16 && text.len() <= 64 {
            self.keys
                .push((key.clone().unbind(), start..self.output.len()));
        }
        Ok(())
    }

    fn string(&mut self, value: &str) {
        self.output.push(b'"');
        let mut remaining = value.as_bytes();
        while !remaining.is_empty() {
            let prefix = plain_string_prefix(remaining);
            self.output.extend_from_slice(&remaining[..prefix]);
            remaining = &remaining[prefix..];
            if let Some((&byte, tail)) = remaining.split_first() {
                match byte {
                    b'"' => self.output.extend_from_slice(b"\\\""),
                    b'\\' => self.output.extend_from_slice(b"\\\\"),
                    b'\n' => self.output.extend_from_slice(b"\\n"),
                    b'\r' => self.output.extend_from_slice(b"\\r"),
                    b'\t' => self.output.extend_from_slice(b"\\t"),
                    8 => self.output.extend_from_slice(b"\\b"),
                    12 => self.output.extend_from_slice(b"\\f"),
                    _ => {
                        const HEX: &[u8] = b"0123456789abcdef";
                        self.output.extend_from_slice(&[
                            b'\\',
                            b'u',
                            b'0',
                            b'0',
                            HEX[usize::from(byte >> 4)],
                            HEX[usize::from(byte & 15)],
                        ]);
                    }
                }
                remaining = tail;
            }
        }
        self.output.push(b'"');
    }

    fn newline(&mut self, depth: usize) {
        if self.option & INDENT != 0 {
            self.output.push(b'\n');
            self.output
                .resize(self.output.len() + (depth + self.base_depth) * 2, b' ');
        }
    }

    #[inline(always)]
    fn scalar(&mut self, value: &Bound<'_, PyAny>) -> PyResult<bool> {
        if value.is_none() {
            self.output.extend_from_slice(b"null");
        } else if let Ok(string) = value.downcast_exact::<PyString>() {
            self.string(
                string
                    .to_str()
                    .map_err(|_| PyTypeError::new_err("str is not valid UTF-8"))?,
            );
        } else if let Ok(boolean) = value.downcast_exact::<PyBool>() {
            self.output
                .extend_from_slice(if boolean.is_true() { b"true" } else { b"false" });
        } else if value.is_exact_instance_of::<PyInt>() {
            let mut buffer = itoa::Buffer::new();
            if let Ok(integer) = value.extract::<i64>() {
                if self.option & STRICT_INTEGER != 0
                    && !(-9_007_199_254_740_991..=9_007_199_254_740_991).contains(&integer)
                {
                    return Err(PyTypeError::new_err("Integer exceeds 53-bit range"));
                }
                self.output
                    .extend_from_slice(buffer.format(integer).as_bytes());
            } else {
                let integer = value
                    .extract::<u64>()
                    .map_err(|_| PyTypeError::new_err("Integer exceeds 64-bit range"))?;
                if self.option & STRICT_INTEGER != 0 && integer > 9_007_199_254_740_991 {
                    return Err(PyTypeError::new_err("Integer exceeds 53-bit range"));
                }
                self.output
                    .extend_from_slice(buffer.format(integer).as_bytes());
            }
        } else if let Ok(float) = value.downcast_exact::<PyFloat>() {
            let number = float.value();
            if number.is_finite() {
                self.output
                    .extend_from_slice(zmij::Buffer::new().format_finite(number).as_bytes());
            } else {
                self.output.extend_from_slice(b"null");
            }
        } else if let Ok(list) = value.downcast_exact::<PyList>() {
            if !list.is_empty() {
                return Ok(false);
            }
            self.output.extend_from_slice(b"[]");
        } else if let Ok(tuple) = value.downcast_exact::<PyTuple>() {
            if !tuple.is_empty() {
                return Ok(false);
            }
            self.output.extend_from_slice(b"[]");
        } else if value.is_exact_instance_of::<PyDict>() {
            return Ok(false);
        } else if let Ok(fragment) = value.downcast_exact::<Fragment>() {
            let fragment = fragment.get();
            let contents = fragment.contents.bind(value.py());
            if let Ok(bytes) = contents.downcast_exact::<PyBytes>() {
                self.output.extend_from_slice(bytes.as_bytes());
            } else if let Ok(text) = contents.downcast_exact::<PyString>() {
                self.output.extend_from_slice(
                    text.to_str()
                        .map_err(|_| {
                            PyTypeError::new_err("str is not valid UTF-8: surrogates not allowed")
                        })?
                        .as_bytes(),
                );
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
        let mut stack: Vec<EncodeContainer<'_>> = Vec::new();
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
                    (EncodeIterator::Dict(dict.iter()), b'{', b'}')
                }
            } else if let Ok(list) = current.downcast_exact::<PyList>() {
                (EncodeIterator::List(list.iter()), b'[', b']')
            } else if let Ok(tuple) = current.downcast_exact::<PyTuple>() {
                (EncodeIterator::Tuple(tuple.iter()), b'[', b']')
            } else {
                return Ok(false);
            };
            self.output.push(opening);
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
                            self.output.push(b',');
                        }
                        frame.count += 1;
                        self.newline(depth);
                        if !self.scalar(&item)? {
                            current = item;
                            continue 'container;
                        }
                    }
                    let frame = stack.pop().expect("unfinished list");
                    if frame.count != 0 {
                        self.newline(stack.len());
                    }
                    self.output.push(frame.closing);
                    continue;
                }
                let item = match &mut frame.iter {
                    EncodeIterator::Dict(iter) => iter.next().map(|(key, item)| (Some(key), item)),
                    EncodeIterator::Sorted(iter) => {
                        iter.next().map(|(key, item)| (Some(key), item))
                    }
                    EncodeIterator::List(iter) => iter.next().map(|item| (None, item)),
                    EncodeIterator::Tuple(iter) => iter.next().map(|item| (None, item)),
                };
                if let Some((key, item)) = item {
                    if frame.count != 0 {
                        self.output.push(b',');
                    }
                    frame.count += 1;
                    self.newline(depth);
                    if let Some(key) = key {
                        if !self.key_any(&key)? {
                            return Ok(false);
                        }
                        self.output.push(b':');
                        if self.option & INDENT != 0 {
                            self.output.push(b' ');
                        }
                    }
                    if !self.scalar(&item)? {
                        current = item;
                        continue 'container;
                    }
                } else {
                    let frame = stack.pop().expect("unfinished container");
                    if frame.count != 0 {
                        self.newline(stack.len());
                    }
                    self.output.push(frame.closing);
                }
            }
        }
    }
}

fn supplied_default<'py>(value: &Bound<'py, PyAny>) -> PyResult<Option<Bound<'py, PyAny>>> {
    // Explicit None is an invalid callback; an omitted argument has no callback
    // cause.
    Ok(Some(value.clone()))
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
    let mut encoder = Encoder {
        output: Vec::with_capacity(256),
        option: flags,
        base_depth: 0,
        dataclass_root: false,
        keys: Vec::new(),
    };
    if encoder.value(&obj)? {
        if flags & APPEND_NEWLINE != 0 {
            encoder.output.push(b'\n');
        }
        return Ok(PyBytes::new(py, &encoder.output).into_any().unbind());
    }
    let fallback = py.import("jsonmodem")?.getattr("_dumps_fallback")?;
    let default_provided = default.is_some();
    Ok(fallback
        .call1((obj, default, option, default_provided))?
        .unbind())
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
    let mut encoder = Encoder {
        output: Vec::with_capacity(256),
        option,
        base_depth: depth,
        dataclass_root: true,
        keys: Vec::new(),
    };
    if encoder.value(fields.as_any())? {
        Ok(Some(PyBytes::new(py, &encoder.output).unbind()))
    } else {
        Ok(None)
    }
}
