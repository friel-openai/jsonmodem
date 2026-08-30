//! Find the first error without building values when a container ending is
//! invalid.

use pyo3::PyResult;

use super::{Decoder, MAX_DECODE_DEPTH, parse_double};

#[inline]
pub(super) fn has_invalid_container_ending(input: &str) -> bool {
    if input.len() < 1024 {
        return false;
    }
    let bytes = input.as_bytes();
    let non_whitespace = |byte: &&u8| !matches!(byte, b' ' | b'\t' | b'\n' | b'\r');
    let closing = match bytes.iter().take(64).find(non_whitespace) {
        Some(b'[') => b']',
        Some(b'{') => b'}',
        _ => return false,
    };
    // Bound the extra work even when a document ends in a long whitespace suffix.
    bytes
        .iter()
        .rev()
        .take(64)
        .find(non_whitespace)
        .is_some_and(|last| *last != closing)
}

impl Decoder<'_, '_> {
    fn validation_string(&mut self) -> PyResult<()> {
        let escaped = self
            .reader
            .string_with_buffer(&mut self.string_buffer)
            .map_err(|error| self.error(error))?
            .is_none();
        if escaped {
            self.release_large_string_buffer();
        }
        Ok(())
    }

    fn validation_key(&mut self) -> PyResult<()> {
        self.validation_string()?;
        self.expect(b':')
    }

    pub(super) fn validate_without_values(&mut self) -> PyResult<()> {
        // The depth limit bounds storage, so each token needs no heap-state check.
        let mut stack = [0_u8; MAX_DECODE_DEPTH];
        let mut depth = 0;
        'next_value: loop {
            match self.reader.peek() {
                Some(b'[') => {
                    if depth >= MAX_DECODE_DEPTH {
                        return Err(self.fail("recursion depth exceeded"));
                    }
                    self.expect(b'[')?;
                    if self.reader.peek() != Some(b']') {
                        stack[depth] = b']';
                        depth += 1;
                        continue;
                    }
                    self.expect(b']')?;
                }
                Some(b'{') => {
                    if depth >= MAX_DECODE_DEPTH {
                        return Err(self.fail("recursion depth exceeded"));
                    }
                    self.expect(b'{')?;
                    if self.reader.peek() != Some(b'}') {
                        self.validation_key()?;
                        stack[depth] = b'}';
                        depth += 1;
                        continue;
                    }
                    self.expect(b'}')?;
                }
                Some(b'"') => self.validation_string()?,
                Some(b'n') => self
                    .reader
                    .literal("null")
                    .map_err(|error| self.error(error))?,
                Some(b't') => self
                    .reader
                    .literal("true")
                    .map_err(|error| self.error(error))?,
                Some(b'f') => self
                    .reader
                    .literal("false")
                    .map_err(|error| self.error(error))?,
                Some(b'-' | b'0'..=b'9') => {
                    let number = self.reader.number().map_err(|error| self.error(error))?;
                    if number.integer.is_none() {
                        let value =
                            parse_double(number.text).map_err(|_| self.fail("invalid number"))?;
                        if !value.is_finite() {
                            return Err(self.fail("number is infinity when parsed as double"));
                        }
                    }
                }
                _ => return Err(self.fail("expected JSON value")),
            }
            loop {
                if depth == 0 {
                    return if self.reader.peek().is_some() {
                        Err(self.fail("unexpected content after document"))
                    } else {
                        Ok(())
                    };
                }
                match stack[depth - 1] {
                    b']' => match self.reader.peek() {
                        Some(b',') => {
                            self.expect(b',')?;
                            continue 'next_value;
                        }
                        Some(b']') => self.expect(b']')?,
                        _ => return Err(self.fail("expected comma or closing bracket")),
                    },
                    _ => match self.reader.peek() {
                        Some(b',') => {
                            self.expect(b',')?;
                            self.validation_key()?;
                            continue 'next_value;
                        }
                        Some(b'}') => self.expect(b'}')?,
                        _ => return Err(self.fail("expected comma or closing brace")),
                    },
                }
                depth -= 1;
            }
        }
    }
}
