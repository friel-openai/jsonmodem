use alloc::vec::Vec;

use super::LexemeBackend;
use crate::context::{EventCtx, PathCtx, PathError, PathKind, ValueCtx};

/// Emits exact-number and string-fragment events without retaining their paths.
///
/// Use `JsonModem<EventBackend>` when event locations are unnecessary. The
/// backend retains parent container kinds for grammar validation, but does not
/// retain property names or count array indices. Use [`LexemeBackend`] when
/// paths are needed to locate values or filter events.
#[derive(Debug, Default, Clone)]
pub struct EventBackend {
    // The stack moves between the parser and each feed's backend, not events.
    parents: Vec<PathKind>,
}

impl PathCtx for EventBackend {
    type PathState = Self;
    type Path = ();

    fn frozen_new(&mut self) -> Self {
        Self::default()
    }

    fn thaw(&mut self, frozen: Self) {
        *self = frozen;
    }

    fn freeze(&mut self, (): ()) -> Self {
        core::mem::take(self)
    }

    fn push_key_from_str(&mut self, (): &mut (), _key: &str) {
        self.parents.push(PathKind::Key);
    }

    fn push_index_zero(&mut self, (): &mut ()) {
        self.parents.push(PathKind::Index);
    }

    fn bump_last_index(&mut self, (): &mut ()) -> Result<(), PathError> {
        match self.parents.last() {
            Some(PathKind::Index) => Ok(()),
            _ => Err(PathError::NotArrayFrame),
        }
    }

    fn pop_kind(&mut self, (): &mut ()) -> Option<PathKind> {
        self.parents.pop()
    }

    fn last_kind(&self, (): &()) -> Option<PathKind> {
        self.parents.last().copied()
    }
}

impl ValueCtx for EventBackend {
    type Null = <LexemeBackend as ValueCtx>::Null;
    type Bool = <LexemeBackend as ValueCtx>::Bool;
    type Num<'src> = <LexemeBackend as ValueCtx>::Num<'src>;
    type Str<'src> = <LexemeBackend as ValueCtx>::Str<'src>;
    type Value = <LexemeBackend as ValueCtx>::Value;
}

impl EventCtx for EventBackend {
    type Error = <LexemeBackend as EventCtx>::Error;

    fn push_key_from_raw_str(&mut self, (): &mut (), _key: &[u8]) {
        self.parents.push(PathKind::Key);
    }

    fn new_null(&mut self) -> Result<Self::Null, Self::Error> {
        LexemeBackend.new_null()
    }

    fn new_bool(&mut self, value: bool) -> Result<Self::Bool, Self::Error> {
        LexemeBackend.new_bool(value)
    }

    fn new_number<'src>(&mut self, value: &'src str) -> Result<Self::Num<'src>, Self::Error> {
        LexemeBackend.new_number(value)
    }

    fn new_number_owned<'a>(
        &mut self,
        value: alloc::string::String,
    ) -> Result<Self::Num<'a>, Self::Error> {
        LexemeBackend.new_number_owned(value)
    }

    fn new_str<'src>(&mut self, value: &'src str) -> Result<Self::Str<'src>, Self::Error> {
        LexemeBackend.new_str(value)
    }

    fn new_str_owned<'a>(
        &mut self,
        value: alloc::string::String,
    ) -> Result<Self::Str<'a>, Self::Error> {
        LexemeBackend.new_str_owned(value)
    }

    fn new_str_raw_owned<'a>(&mut self, value: Vec<u8>) -> Result<Self::Str<'a>, Self::Error> {
        LexemeBackend.new_str_raw_owned(value)
    }
}

#[cfg(test)]
mod tests {
    use alloc::{
        format,
        string::{String, ToString},
        vec,
        vec::Vec,
    };

    use super::*;
    use crate::{JsonModem, ParserOptions};

    fn events<Ctx: EventCtx + Default>(
        chunks: &[&str],
        options: ParserOptions,
    ) -> Vec<Result<String, (String, usize, usize)>> {
        let mut parser = JsonModem::<Ctx>::new(options);
        let mut events = Vec::new();
        for chunk in chunks {
            events.extend(parser.feed(chunk).to_iter().map(|event| {
                event
                    .map(|event| format!("{:?}", event.with_path(())))
                    .map_err(|error| (error.to_string(), error.line(), error.column()))
            }));
        }
        events.extend(parser.finish().to_iter().map(|event| {
            event
                .map(|event| format!("{:?}", event.with_path(())))
                .map_err(|error| (error.to_string(), error.line(), error.column()))
        }));
        events
    }

    fn assert_same_events(chunks: &[&str], options: ParserOptions) {
        assert_eq!(
            events::<EventBackend>(chunks, options),
            events::<LexemeBackend>(chunks, options),
            "chunks: {chunks:?}",
        );
    }

    #[test]
    fn memory_safety_untracked_events_at_every_character_boundary() {
        for text in [
            r#"{"key":[{},[],true,false,null,"text","a\nb\uD83D\uDE00",9007199254740993,18446744073709551615,-1.25e3]}"#,
            "{\"\u{e9}\":\"\u{1f600}\",\"\\u0061\":2,\"\":0}",
            "0",
            "1e2",
            r#"{"key":[0,]}"#,
            r#"{"bad\q":null}"#,
            r#"{"bad\ud800":null}"#,
            "[1e400]",
            "[123",
            "[\ntrue false]",
        ] {
            for index in 0..=text.len() {
                if text.is_char_boundary(index) {
                    assert_same_events(&[&text[..index], &text[index..]], ParserOptions::new());
                }
            }
            let chunks: Vec<_> = text
                .char_indices()
                .map(|(index, ch)| &text[index..index + ch.len_utf8()])
                .collect();
            assert_same_events(&chunks, ParserOptions::new());
        }
    }

    #[test]
    fn memory_safety_untracked_multiple_roots_and_decode_modes() {
        for mode in [
            crate::DecodeMode::StrictUnicode,
            crate::DecodeMode::ReplaceInvalid,
            crate::DecodeMode::SurrogatePreserving,
        ] {
            assert_same_events(
                &[r#"{"first":["a"#, r#"\ud800",7]}{}[[],{}] false 1e2"#],
                ParserOptions::new()
                    .with_decode_mode(mode)
                    .with_allow_multiple_json_values(true),
            );
        }
    }

    #[test]
    fn memory_safety_untracked_depth_limit_is_unchanged() {
        for depth in [255, 256, 257] {
            let text = format!("{}0{}", "[".repeat(depth), "]".repeat(depth));
            let result = events::<EventBackend>(&[&text], ParserOptions::new());
            assert_eq!(result.iter().any(Result::is_err), depth > 256);
            assert_same_events(&[&text], ParserOptions::new());
        }
    }

    #[test]
    fn memory_safety_untracked_early_drop_restores_structure() {
        let mut minimal = JsonModem::<EventBackend>::new(ParserOptions::new());
        let mut tracked = JsonModem::<LexemeBackend>::new(ParserOptions::new());
        for chunk in [r#"{"key":[1,"two"#, r#"",false],"next":null}"#] {
            {
                let mut left = minimal.feed(chunk).to_iter();
                let mut right = tracked.feed(chunk).to_iter();
                assert_eq!(
                    left.next().map(|event| format!("{:?}", event.unwrap())),
                    right
                        .next()
                        .map(|event| format!("{:?}", event.unwrap().with_path(()))),
                );
            }
            let left: Vec<_> = minimal
                .feed("")
                .to_iter()
                .map(|event| format!("{:?}", event.unwrap()))
                .collect();
            let right: Vec<_> = tracked
                .feed("")
                .to_iter()
                .map(|event| format!("{:?}", event.unwrap().with_path(())))
                .collect();
            assert_eq!(left, right);
        }
        assert_eq!(
            minimal.finish().to_iter().count(),
            tracked.finish().to_iter().count()
        );
    }

    #[test]
    fn untracked_events_do_not_own_the_structural_stack() {
        let mut parser = JsonModem::<EventBackend>::new(ParserOptions::new());
        let retained: Vec<_> = parser.feed(r#"{"key":[true]}"#).to_iter().collect();
        assert!(retained.iter().all(Result::is_ok));
        assert_eq!(retained.len(), 5);
        assert!(parser.finish().to_iter().next().is_none());
        assert_eq!(*retained[2].as_ref().unwrap().path(), ());
        let mut backend = EventBackend::default();
        backend.push_key_from_str(&mut (), "not retained");
        backend.push_index_zero(&mut ());
        assert_eq!(backend.parents, vec![PathKind::Key, PathKind::Index]);
        backend.bump_last_index(&mut ()).unwrap();
        assert_eq!(backend.parents, vec![PathKind::Key, PathKind::Index]);
    }
}
