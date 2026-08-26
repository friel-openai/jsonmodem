//! Borrowed tokens for complete JSON documents, without incremental events or
//! paths.

use alloc::{borrow::Cow, string::String};

/// A syntax failure at a UTF-8 byte offset in the input document.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct DocumentError {
    /// Explanation of the rejected token.
    pub message: &'static str,
    /// Byte offset from the start of the document.
    pub offset: usize,
}

/// The original text and numeric category of one syntactically valid JSON
/// number.
pub struct NumberToken<'a> {
    /// Original number text, without delimiters.
    pub text: &'a str,
    /// Whether the token contains a fraction or exponent.
    pub is_float: bool,
}

/// A cursor for a complete UTF-8 document. Consumers build containers directly.
pub struct DocumentReader<'a> {
    input: &'a str,
    offset: usize,
}

impl<'a> DocumentReader<'a> {
    /// Start at the beginning of a validated UTF-8 document.
    #[must_use]
    pub fn new(input: &'a str) -> Self {
        Self { input, offset: 0 }
    }

    /// Current byte offset.
    #[must_use]
    pub fn offset(&self) -> usize {
        self.offset
    }

    /// Return the next byte, after JSON whitespace only.
    pub fn peek(&mut self) -> Option<u8> {
        while self
            .input
            .as_bytes()
            .get(self.offset)
            .is_some_and(|b| matches!(b, b' ' | b'\t' | b'\r' | b'\n'))
        {
            self.offset += 1;
        }
        self.input.as_bytes().get(self.offset).copied()
    }

    /// Consume one expected byte, ignoring preceding JSON whitespace.
    ///
    /// # Errors
    /// Returns an error if the byte differs or input has ended.
    pub fn expect(&mut self, byte: u8) -> Result<(), DocumentError> {
        if self.peek() != Some(byte) {
            return Err(self.error("unexpected character or end of input"));
        }
        self.offset += 1;
        Ok(())
    }

    /// Consume one JSON literal; its delimiter is checked by the caller.
    ///
    /// # Errors
    /// Returns an error if the remaining bytes do not start with the literal.
    pub fn literal(&mut self, literal: &str) -> Result<(), DocumentError> {
        if !self.input.as_bytes()[self.offset..].starts_with(literal.as_bytes()) {
            return Err(self.error("invalid literal"));
        }
        self.offset += literal.len();
        Ok(())
    }

    /// Make a syntax error at the current position.
    #[must_use]
    pub fn error(&self, message: &'static str) -> DocumentError {
        DocumentError {
            message,
            offset: self.offset,
        }
    }

    /// Read a JSON string, allocating only when it contains escapes.
    ///
    /// # Errors
    /// Rejects incomplete strings, controls, invalid escapes, and unpaired
    /// surrogates.
    pub fn string(&mut self) -> Result<Cow<'a, str>, DocumentError> {
        self.expect(b'"')?;
        let mut start = self.offset;
        let mut decoded: Option<String> = None;
        loop {
            let remaining = &self.input.as_bytes()[self.offset..];
            self.offset += plain_string_prefix(remaining);
            let Some(byte) = self.input.as_bytes().get(self.offset).copied() else {
                return Err(self.error("unterminated string"));
            };
            if byte == b'"' {
                let text = &self.input[start..self.offset];
                self.offset += 1;
                return Ok(match decoded {
                    Some(mut owned) => {
                        owned.push_str(text);
                        Cow::Owned(owned)
                    }
                    None => Cow::Borrowed(text),
                });
            }
            if byte < 0x20 {
                return Err(self.error("unescaped control character"));
            }
            let output = decoded.get_or_insert_with(|| String::with_capacity(64));
            output.push_str(&self.input[start..self.offset]);
            let escape_start = self.offset;
            self.offset += 1;
            let escape = self
                .input
                .as_bytes()
                .get(self.offset)
                .copied()
                .ok_or_else(|| self.error("incomplete escape"))?;
            self.offset += 1;
            match escape {
                b'"' => output.push('"'),
                b'\\' => output.push('\\'),
                b'/' => output.push('/'),
                b'b' => output.push('\u{0008}'),
                b'f' => output.push('\u{000c}'),
                b'n' => output.push('\n'),
                b'r' => output.push('\r'),
                b't' => output.push('\t'),
                b'u' => {
                    let mut code = self.hex4().map_err(|_| DocumentError {
                        message: "invalid escaped sequence in string",
                        offset: escape_start,
                    })?;
                    if (0xd800..=0xdbff).contains(&code) {
                        if !self.input[self.offset..].starts_with("\\u") {
                            return Err(self.error("no low surrogate in string"));
                        }
                        let low_start = self.offset;
                        self.offset += 2;
                        let low = self.hex4().map_err(|_| DocumentError {
                            message: "invalid escaped sequence in string",
                            offset: low_start,
                        })?;
                        if !(0xdc00..=0xdfff).contains(&low) {
                            return Err(DocumentError {
                                message: "invalid low surrogate in string",
                                offset: low_start,
                            });
                        }
                        code = 0x10000 + ((code - 0xd800) << 10) + low - 0xdc00;
                    }
                    output.push(char::from_u32(code).ok_or(DocumentError {
                        message: "invalid high surrogate in string",
                        offset: escape_start,
                    })?);
                }
                _ => {
                    return Err(DocumentError {
                        message: "invalid escaped character in string",
                        offset: self.offset - 1,
                    });
                }
            }
            start = self.offset;
        }
    }

    fn hex4(&mut self) -> Result<u32, DocumentError> {
        let mut value = 0;
        for _ in 0..4 {
            let byte = *self
                .input
                .as_bytes()
                .get(self.offset)
                .ok_or_else(|| self.error("incomplete Unicode escape"))?;
            let digit = match byte {
                b'0'..=b'9' => byte - b'0',
                b'a'..=b'f' => byte - b'a' + 10,
                b'A'..=b'F' => byte - b'A' + 10,
                _ => return Err(self.error("invalid Unicode escape")),
            };
            value = value * 16 + u32::from(digit);
            self.offset += 1;
        }
        Ok(value)
    }

    /// Read a number through its end, including a number at end of input.
    ///
    /// # Errors
    /// Rejects missing digits in the integer, fraction, or exponent.
    pub fn number(&mut self) -> Result<NumberToken<'a>, DocumentError> {
        let start = self.offset;
        let bytes = self.input.as_bytes();
        if bytes.get(self.offset) == Some(&b'-') {
            self.offset += 1;
        }
        match bytes.get(self.offset) {
            Some(b'0') => self.offset += 1,
            Some(b'1'..=b'9') => {
                self.offset += 1;
                self.digits();
            }
            _ => return Err(self.error("expected digit")),
        }
        let mut is_float = false;
        if bytes.get(self.offset) == Some(&b'.') {
            is_float = true;
            self.offset += 1;
            if self.digits() == 0 {
                return Err(self.error("expected fraction digit"));
            }
        }
        if matches!(bytes.get(self.offset), Some(b'e' | b'E')) {
            is_float = true;
            self.offset += 1;
            if matches!(bytes.get(self.offset), Some(b'+' | b'-')) {
                self.offset += 1;
            }
            if self.digits() == 0 {
                return Err(self.error("expected exponent digit"));
            }
        }
        Ok(NumberToken {
            text: &self.input[start..self.offset],
            is_float,
        })
    }

    fn digits(&mut self) -> usize {
        let start = self.offset;
        while self
            .input
            .as_bytes()
            .get(self.offset)
            .is_some_and(u8::is_ascii_digit)
        {
            self.offset += 1;
        }
        self.offset - start
    }
}

/// Count string bytes before a quote, backslash, or unescaped control byte.
/// All word loads use checked slices; non-ASCII bytes are copied unchanged.
#[must_use]
#[allow(clippy::missing_panics_doc)] // Checked chunks always contain eight bytes.
pub fn plain_string_prefix(bytes: &[u8]) -> usize {
    const HIGH: u64 = 0x8080_8080_8080_8080;
    const ONES: u64 = 0x0101_0101_0101_0101;
    let mut index = 0;
    while bytes.len() - index >= 64 {
        let chunk = &bytes[index..index + 32];
        let mut special = 0;
        for word in chunk.chunks_exact(8) {
            let word = u64::from_ne_bytes(word.try_into().expect("eight-byte slice"));
            let quote = word ^ 0x2222_2222_2222_2222;
            let slash = word ^ 0x5c5c_5c5c_5c5c_5c5c;
            special |= (quote.wrapping_sub(ONES) & !quote)
                | (slash.wrapping_sub(ONES) & !slash)
                | (word.wrapping_sub(0x2020_2020_2020_2020) & !word);
        }
        if special & HIGH != 0 {
            break;
        }
        index += 32;
    }
    while let Some(chunk) = bytes.get(index..index + 8) {
        let word = u64::from_ne_bytes(chunk.try_into().expect("eight-byte slice"));
        let quote = word ^ 0x2222_2222_2222_2222;
        let slash = word ^ 0x5c5c_5c5c_5c5c_5c5c;
        let special = (quote.wrapping_sub(ONES) & !quote)
            | (slash.wrapping_sub(ONES) & !slash)
            | (word.wrapping_sub(0x2020_2020_2020_2020) & !word);
        if special & HIGH != 0 {
            break;
        }
        index += 8;
    }
    while let Some(&byte) = bytes.get(index) {
        if byte < 0x20 || matches!(byte, b'"' | b'\\') {
            break;
        }
        index += 1;
    }
    index
}

#[cfg(test)]
mod tests {
    use alloc::{format, vec};

    use super::*;

    #[test]
    fn checked_word_scan_matches_scalar_at_every_alignment() {
        let lengths = if cfg!(miri) { 12 } else { 160 };
        for length in 0..lengths {
            let mut bytes = vec![b'x'; length];
            for position in 0..length {
                for byte in 0..=u8::MAX {
                    bytes[position] = byte;
                    let expected = bytes
                        .iter()
                        .position(|&b| b < 32 || matches!(b, b'"' | b'\\'))
                        .unwrap_or(length);
                    assert_eq!(plain_string_prefix(&bytes), expected);
                }
                bytes[position] = b'x';
            }
        }
    }

    #[test]
    fn escaped_unicode_and_truncation() {
        for (input, expected) in [
            (r#""\uD83D\uDE42""#, "\u{1f642}"),
            (r#""\b\f\n\r\t\/\\\"""#, "\u{8}\u{c}\n\r\t/\\\""),
        ] {
            assert_eq!(DocumentReader::new(input).string().unwrap(), expected);
            for end in 0..input.len() {
                assert!(DocumentReader::new(&input[..end]).string().is_err());
            }
        }
        for escape in [
            "\\uDC00",
            "\\uD800",
            "\\uD800\\u0000",
            "\\u0x00",
            "\\x",
            "\n",
        ] {
            assert!(
                DocumentReader::new(&format!("\"{escape}\""))
                    .string()
                    .is_err()
            );
        }
    }

    #[test]
    fn number_eof_and_invalid_fraction() {
        for input in ["0", "-0", "9007199254740993", "-123.456e-7"] {
            let mut reader = DocumentReader::new(input);
            assert_eq!(reader.number().unwrap().text, input);
            assert_eq!(reader.peek(), None);
        }
        for input in ["-", "1.", "1.e2", "1e", "1e+"] {
            assert!(DocumentReader::new(input).number().is_err());
        }
    }
}
