//! Complete-document operations: no streaming events and no Python
//! preprocessing.

use std::collections::HashMap;

use jsonmodem::document::{DocumentError, DocumentReader, plain_string_prefix};
use pyo3::{
    exceptions::PyTypeError,
    prelude::*,
    types::{
        PyBool, PyByteArray, PyBytes, PyDict, PyFloat, PyInt, PyList, PyMemoryView, PyString,
        PyTuple,
        iter::{BoundDictIterator, BoundListIterator, BoundTupleIterator},
    },
};

const MAX_DEPTH: usize = 256;
const INDENT: i32 = 1;
const SORT_KEYS: i32 = 32;
const STRICT_INTEGER: i32 = 64;
const APPEND_NEWLINE: i32 = 1024;

/// One document's container construction and bounded cache of repeated keys.
struct Decoder<'py, 'src> {
    py: Python<'py>,
    input: &'src str,
    reader: DocumentReader<'src>,
    keys: HashMap<String, Py<PyString>>,
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
                        self.keys.insert(text.into_owned(), key.clone_ref(self.py));
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
                    if stack.len() >= MAX_DEPTH {
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
                    if stack.len() >= MAX_DEPTH {
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
                        py.get_type::<PyInt>()
                            .call1((number.text,))
                            .map(|value| value.unbind())
                            .map_err(|_| self.fail("integer exceeds Python conversion limit"))?
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
pub fn loads(py: Python<'_>, input: Bound<'_, PyAny>) -> PyResult<PyObject> {
    if let Ok(text) = input.downcast::<PyString>() {
        let text = text
            .to_str()
            .map_err(|_| super::json_decode_error(py, "str is not valid UTF-8", "", 0))?;
        return decode(py, text);
    }
    if let Ok(bytes) = input.downcast::<PyBytes>() {
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
            return Err(PyTypeError::new_err(
                "memoryview must be backed by bytes or bytearray",
            ));
        }
        if !input.getattr("c_contiguous")?.extract::<bool>()?
            || input.getattr("itemsize")?.extract::<usize>()? != 1
        {
            return Err(PyTypeError::new_err("memoryview must be contiguous bytes"));
        }
        let bytes = input.call_method0("tobytes")?;
        return decode_bytes(py, bytes.downcast::<PyBytes>()?.as_bytes());
    }
    Err(PyTypeError::new_err(
        "loads() expected str, bytes, bytearray, or memoryview",
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
    // Retained owners make identity-based reuse safe for the whole call.
    keys: Vec<(Py<PyString>, Vec<u8>)>,
}

/// Owning iterators keep each container alive without native recursion.
enum EncodeIterator<'py> {
    Dict(BoundDictIterator<'py>),
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
    fn key(&mut self, key: &Bound<'_, PyString>) -> PyResult<()> {
        let cache = self.output.len() >= 1024;
        if cache {
            if let Some((_, encoded)) = self
                .keys
                .iter()
                .find(|(owner, _)| owner.as_ptr() == key.as_ptr())
            {
                self.output.extend_from_slice(encoded);
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
                .push((key.clone().unbind(), self.output[start..].to_vec()));
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
            self.output.resize(self.output.len() + depth * 2, b' ');
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
                    .extend_from_slice(ryu::Buffer::new().format_finite(number).as_bytes());
            } else {
                self.output.extend_from_slice(b"null");
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
            if stack.len() >= MAX_DEPTH {
                return Err(PyTypeError::new_err("recursion depth exceeded"));
            }
            let identity = current.as_ptr() as usize;
            if stack.iter().any(|frame| frame.identity == identity) {
                return Err(PyTypeError::new_err("circular reference"));
            }
            let (iter, opening, closing) = if let Ok(dict) = current.downcast_exact::<PyDict>() {
                if self.option & SORT_KEYS != 0 {
                    return Ok(false);
                }
                (EncodeIterator::Dict(dict.iter()), b'{', b'}')
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
                        let Ok(key) = key.downcast_exact::<PyString>() else {
                            return Ok(false);
                        };
                        self.key(key)?;
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

/// Serialize common JSON types directly, preserving the uncommon-type fallback.
#[pyfunction]
#[pyo3(signature=(obj, /, default=None, option=None))]
pub fn dumps(
    py: Python<'_>,
    obj: Bound<'_, PyAny>,
    default: Option<Bound<'_, PyAny>>,
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
    if default
        .as_ref()
        .is_some_and(|value| !value.is_none() && !value.is_callable())
    {
        return Err(PyTypeError::new_err("default must be callable"));
    }
    let mut encoder = Encoder {
        output: Vec::with_capacity(256),
        option: flags,
        keys: Vec::new(),
    };
    if encoder.value(&obj)? {
        if flags & APPEND_NEWLINE != 0 {
            encoder.output.push(b'\n');
        }
        return Ok(PyBytes::new(py, &encoder.output).into_any().unbind());
    }
    let fallback = py.import("jsonmodem")?.getattr("_dumps_fallback")?;
    Ok(fallback.call1((obj, default, option))?.unbind())
}
