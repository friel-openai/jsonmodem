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
    /// Integer conversion performed while scanning, when it fits a 64-bit type.
    pub integer: Option<IntegerToken>,
}

/// An exact integer in the signed or unsigned 64-bit range.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum IntegerToken {
    /// Negative integers and nonnegative integers through `i64::MAX`.
    Signed(i64),
    /// Nonnegative integers above `i64::MAX` through `u64::MAX`.
    Unsigned(u64),
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
        let mut decoded = String::new();
        Ok(match self.string_with_buffer(&mut decoded)? {
            Some(text) => Cow::Borrowed(text),
            None => Cow::Owned(decoded),
        })
    }

    /// Read a JSON string, reusing `decoded` when the string contains escapes.
    ///
    /// Returns the input text for an unescaped string. Otherwise returns `None`
    /// and replaces `decoded` with the decoded string, retaining its capacity.
    /// A caller must copy decoded text before reusing the buffer.
    ///
    /// # Errors
    /// Rejects incomplete strings, controls, invalid escapes, and unpaired
    /// surrogates.
    #[inline]
    pub fn string_with_buffer(
        &mut self,
        decoded: &mut String,
    ) -> Result<Option<&'a str>, DocumentError> {
        self.expect(b'"')?;
        let start = self.offset;
        self.offset += plain_string_prefix(&self.input.as_bytes()[start..]);
        match self.input.as_bytes().get(self.offset).copied() {
            Some(b'"') => {
                let text = &self.input[start..self.offset];
                self.offset += 1;
                Ok(Some(text))
            }
            None => Err(self.error("unterminated string")),
            Some(byte) if byte < 0x20 => Err(self.error("unescaped control character")),
            Some(_) => {
                self.string_escaped(start, decoded)?;
                Ok(None)
            }
        }
    }

    fn string_escaped(
        &mut self,
        mut start: usize,
        decoded: &mut String,
    ) -> Result<(), DocumentError> {
        decoded.clear();
        // The first escape can add four UTF-8 bytes after the plain prefix.
        decoded.reserve(64.max(self.offset - start + 4));
        loop {
            decoded.push_str(&self.input[start..self.offset]);
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
                b'"' => decoded.push('"'),
                b'\\' => decoded.push('\\'),
                b'/' => decoded.push('/'),
                b'b' => decoded.push('\u{0008}'),
                b'f' => decoded.push('\u{000c}'),
                b'n' => decoded.push('\n'),
                b'r' => decoded.push('\r'),
                b't' => decoded.push('\t'),
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
                    decoded.push(char::from_u32(code).ok_or(DocumentError {
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
            let remaining = &self.input.as_bytes()[start..];
            self.offset += if remaining.len() < 8 {
                scalar_string_prefix::<false>(remaining)
            } else {
                plain_string_prefix(remaining)
            };
            match self.input.as_bytes().get(self.offset).copied() {
                Some(b'"') => {
                    decoded.push_str(&self.input[start..self.offset]);
                    self.offset += 1;
                    return Ok(());
                }
                None => return Err(self.error("unterminated string")),
                Some(byte) if byte < 0x20 => {
                    return Err(self.error("unescaped control character"));
                }
                Some(_) => {}
            }
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
        let negative = bytes.get(self.offset) == Some(&b'-');
        if negative {
            self.offset += 1;
        }
        let magnitude = match bytes.get(self.offset) {
            Some(b'0') => {
                self.offset += 1;
                Some(0)
            }
            Some(&first @ b'1'..=b'9') => {
                self.offset += 1;
                self.integer_digits(first - b'0')
            }
            _ => return Err(self.error("expected digit")),
        };
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
            integer: if is_float {
                None
            } else {
                magnitude.and_then(|value| {
                    if let Ok(value) = i64::try_from(value) {
                        Some(IntegerToken::Signed(if negative { -value } else { value }))
                    } else if !negative {
                        Some(IntegerToken::Unsigned(value))
                    } else if value == i64::MIN.unsigned_abs() {
                        Some(IntegerToken::Signed(i64::MIN))
                    } else {
                        None
                    }
                })
            },
        })
    }

    fn integer_digits(&mut self, first: u8) -> Option<u64> {
        let bytes = self.input.as_bytes();
        let mut value = u64::from(first);
        // The first digit and up to eighteen more always fit in u64.
        let end = self.offset.saturating_add(18).min(bytes.len());
        while self.offset < end {
            let byte = bytes[self.offset];
            let digit = byte.wrapping_sub(b'0');
            if digit > 9 {
                return Some(value);
            }
            value = value * 10 + u64::from(digit);
            self.offset += 1;
        }
        let Some(byte) = bytes.get(self.offset) else {
            return Some(value);
        };
        let digit = byte.wrapping_sub(b'0');
        if digit > 9 {
            return Some(value);
        }
        self.offset += 1;
        let value = value
            .checked_mul(10)
            .and_then(|value| value.checked_add(u64::from(digit)));
        if self.digits() == 0 { value } else { None }
    }

    fn digits(&mut self) -> usize {
        let bytes = &self.input.as_bytes()[self.offset..];
        let mut count = 0;
        while let Some(chunk) = bytes.get(count..count + 8) {
            let word = u64::from_ne_bytes(chunk.try_into().expect("eight-byte slice"));
            // Rust's double parser uses this predicate for eight ASCII digits.
            let upper = word.wrapping_add(0x4646_4646_4646_4646);
            let lower = word.wrapping_sub(0x3030_3030_3030_3030);
            if (upper | lower) & 0x8080_8080_8080_8080 != 0 {
                break;
            }
            count += 8;
        }
        while bytes.get(count).is_some_and(u8::is_ascii_digit) {
            count += 1;
        }
        self.offset += count;
        count
    }
}

/// Count string bytes before a quote, backslash, or unescaped control byte.
/// All word loads use checked slices; non-ASCII bytes are copied unchanged.
#[must_use]
#[inline]
pub fn plain_string_prefix(bytes: &[u8]) -> usize {
    string_prefix::<false>(bytes)
}

// The incremental scanner counts non-ASCII characters separately from bytes.
#[inline]
pub(crate) fn ascii_string_prefix(bytes: &[u8]) -> usize {
    string_prefix::<true>(bytes)
}

fn string_prefix<const ASCII_ONLY: bool>(bytes: &[u8]) -> usize {
    let mut index = 0;
    // Most keys and values end before a full vector-sized chunk.
    for _ in 0..2 {
        let Some(chunk) = bytes.get(index..index + 8) else {
            return index + scalar_string_prefix::<ASCII_ONLY>(&bytes[index..]);
        };
        let word = u64::from_le_bytes(chunk.try_into().expect("eight-byte slice"));
        let special = string_special_mask::<ASCII_ONLY>(word);
        if special != 0 {
            return index + special.trailing_zeros() as usize / 8;
        }
        index += 8;
    }
    while bytes.len() - index >= 32 {
        let chunk: &[u8; 32] = bytes[index..index + 32].try_into().expect("32-byte slice");
        let special = chunk.map(|byte| {
            u8::from(byte < 0x20)
                | u8::from(byte == b'"')
                | u8::from(byte == b'\\')
                | u8::from(ASCII_ONLY && !byte.is_ascii())
        });
        if special.into_iter().fold(0, |found, byte| found | byte) != 0 {
            break;
        }
        index += 32;
    }
    while let Some(chunk) = bytes.get(index..index + 8) {
        let word = u64::from_le_bytes(chunk.try_into().expect("eight-byte slice"));
        let special = string_special_mask::<ASCII_ONLY>(word);
        if special != 0 {
            return index + special.trailing_zeros() as usize / 8;
        }
        index += 8;
    }
    index + scalar_string_prefix::<ASCII_ONLY>(&bytes[index..])
}

#[inline]
fn string_special_mask<const ASCII_ONLY: bool>(word: u64) -> u64 {
    const HIGH: u64 = 0x8080_8080_8080_8080;
    const ONES: u64 = 0x0101_0101_0101_0101;
    let quote = word ^ 0x2222_2222_2222_2222;
    let slash = word ^ 0x5c5c_5c5c_5c5c_5c5c;
    // Subtraction can mark later bytes too; the first marked byte is exact.
    // Little-endian loads put that byte at the least-significant set bit.
    ((quote.wrapping_sub(ONES) & !quote)
        | (slash.wrapping_sub(ONES) & !slash)
        | (word.wrapping_sub(0x2020_2020_2020_2020) & !word)
        | if ASCII_ONLY { word } else { 0 })
        & HIGH
}

#[inline]
fn scalar_string_prefix<const ASCII_ONLY: bool>(bytes: &[u8]) -> usize {
    bytes
        .iter()
        .position(|&byte| {
            byte < 0x20 || matches!(byte, b'"' | b'\\') || (ASCII_ONLY && !byte.is_ascii())
        })
        .unwrap_or(bytes.len())
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
                    let ascii_expected = bytes
                        .iter()
                        .position(|&b| !(32..128).contains(&b) || matches!(b, b'"' | b'\\'))
                        .unwrap_or(length);
                    assert_eq!(ascii_string_prefix(&bytes), ascii_expected);
                }
                bytes[position] = b'x';
            }
        }
    }

    #[test]
    fn checked_wide_scan_at_unaligned_starts() {
        for alignment in [0, 1, 7] {
            let mut storage = [b'x'; 104];
            let bytes = &mut storage[alignment..alignment + 96];
            for position in [0, 15, 16, 31, 32, 63, 64, 95] {
                for byte in [b'"', b'\\', b'\n', 0xff] {
                    bytes[position] = byte;
                    assert_eq!(
                        plain_string_prefix(bytes),
                        if byte == 0xff { bytes.len() } else { position },
                    );
                    assert_eq!(ascii_string_prefix(bytes), position);
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
    fn string_buffer_reuses_storage_without_changing_borrowed_text() {
        let input = r#""first\nvalue" "plain" "\uD83D\uDE42" "" "last\tvalue""#;
        let mut reader = DocumentReader::new(input);
        let mut buffer = String::with_capacity(128);
        let storage = buffer.as_ptr();

        assert_eq!(reader.string_with_buffer(&mut buffer).unwrap(), None);
        assert_eq!(buffer, "first\nvalue");
        let plain = reader.string_with_buffer(&mut buffer).unwrap().unwrap();
        assert_eq!(plain, "plain");
        assert_eq!(reader.string_with_buffer(&mut buffer).unwrap(), None);
        assert_eq!(buffer, "\u{1f642}");
        assert_eq!(reader.string_with_buffer(&mut buffer).unwrap(), Some(""));
        assert_eq!(reader.string_with_buffer(&mut buffer).unwrap(), None);
        assert_eq!(buffer, "last\tvalue");
        assert_eq!(buffer.as_ptr(), storage);
        assert_eq!(plain, "plain");
        assert_eq!(reader.peek(), None);
    }

    #[test]
    fn string_buffer_keeps_escape_error_positions() {
        for (token, message, offset) in [
            (r#""\q""#, "invalid escaped character in string", 2),
            (r#""\uZZZZ""#, "invalid escaped sequence in string", 1),
            (r#""\uD800\uZZZZ""#, "invalid escaped sequence in string", 7),
            (r#""\uD800\u1234""#, "invalid low surrogate in string", 7),
            (r#""\uDC00""#, "invalid high surrogate in string", 1),
        ] {
            let mut buffer = String::from("previous decoded value");
            assert_eq!(
                DocumentReader::new(token).string_with_buffer(&mut buffer),
                Err(DocumentError { message, offset }),
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

    fn check_integer(input: &str) {
        let mut reader = DocumentReader::new(input);
        let number = reader.number().unwrap();
        let expected = input
            .parse::<i64>()
            .map(IntegerToken::Signed)
            .or_else(|_| input.parse::<u64>().map(IntegerToken::Unsigned))
            .ok();
        assert_eq!(number.integer, expected, "{input}");
        assert_eq!(number.text, input);
        assert!(!number.is_float);
        assert_eq!(reader.offset(), input.len());
    }

    #[test]
    fn integer_conversion_boundaries() {
        check_integer("0");
        check_integer("-0");
        for bits in 0..=64 {
            let boundary = 1u128 << bits;
            for value in [boundary - 1, boundary, boundary + 1] {
                check_integer(&format!("{value}"));
                check_integer(&format!("-{value}"));
            }
        }
        let limit = if cfg!(miri) { 32 } else { 310 };
        for digits in 1..limit {
            let input = "9".repeat(digits);
            check_integer(&input);
            check_integer(&format!("-{input}"));
        }
    }

    #[test]
    fn fractions_and_exponents_do_not_return_integer_values() {
        for input in [
            "0.0",
            "-0.0",
            "-0e-1000",
            "1e+0",
            "18446744073709551615.0",
            "18446744073709551616.0",
            "999999999999999999999999999999999999999999999e-40",
        ] {
            let mut reader = DocumentReader::new(input);
            let number = reader.number().unwrap();
            assert_eq!(number.integer, None, "{input}");
            assert!(number.is_float);
            assert_eq!(number.text, input);
            assert_eq!(reader.offset(), input.len());
        }
    }

    #[test]
    fn number_errors_preserve_offsets() {
        for (input, message, offset) in [
            ("-", "expected digit", 1),
            ("1.", "expected fraction digit", 2),
            ("1.e2", "expected fraction digit", 2),
            ("1e", "expected exponent digit", 2),
            ("1e+", "expected exponent digit", 3),
            ("18446744073709551616.", "expected fraction digit", 21),
            ("18446744073709551616e-", "expected exponent digit", 22),
        ] {
            let error = DocumentReader::new(input).number().err();
            assert_eq!(error, Some(DocumentError { message, offset }));
        }
    }

    #[test]
    fn digit_scans_match_scalar_for_ascii_and_utf8() {
        let lengths = if cfg!(miri) { 12 } else { 96 };
        for length in 0..lengths {
            let start = length % 16;
            let prefix = format!("{}{}", " ".repeat(start), "9".repeat(length));
            let mut reader = DocumentReader::new(&prefix);
            reader.offset = start;
            assert_eq!(reader.digits(), length);
            assert_eq!(reader.offset(), prefix.len());
            for position in 0..length {
                for byte in 0..=u8::MAX {
                    let input = format!(
                        "{}{}{}",
                        &prefix[..start + position],
                        char::from(byte),
                        &prefix[start + position + 1..],
                    );
                    let expected = input.as_bytes()[start..]
                        .iter()
                        .take_while(|byte| byte.is_ascii_digit())
                        .count();
                    let mut reader = DocumentReader::new(&input);
                    reader.offset = start;
                    assert_eq!(reader.digits(), expected, "{input:?}");
                    assert_eq!(reader.offset(), start + expected);
                }
            }
        }
        for suffix in ["\u{800}", "\u{ffff}", "\u{10000}", "\u{10ffff}"] {
            for length in 0..32 {
                let input = format!("{}{suffix}7", "0".repeat(length));
                let mut reader = DocumentReader::new(&input);
                assert_eq!(reader.digits(), length);
                assert_eq!(reader.offset(), length);
            }
        }
    }
}
