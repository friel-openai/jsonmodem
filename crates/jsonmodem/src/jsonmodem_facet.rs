#![allow(missing_docs)]

use alloc::{borrow::Cow, boxed::Box, collections::VecDeque, string::ToString, vec::Vec};
use core::{cell::Cell, fmt};

use facet::Facet;
use facet_deserialize::{
    DeserError, DeserErrorKind, Instruction, Outcome, PopReason, Scalar, Span, Spanned,
    StackRunner, ValueReason,
};
use facet_reflect::{Partial, ReflectError};

use crate::{
    backend::{StdBackend, StdValueAssembler},
    buffer_options::BufferOptions,
    jsonmodem_buffers::{BufferError, BufferedEvent, JsonModemBuffers},
    lending_iterator::LendingIterator,
    parser::{ParserError, ParserOptions},
    path::{Path, PathItem},
};

type BufferIter<'a> =
    crate::jsonmodem_buffers::JsonModemBuffersIter<'a, StdBackend, StdValueAssembler>;
type BufferClosed = crate::jsonmodem_buffers::JsonModemBuffersClosed<StdBackend, StdValueAssembler>;

/// Configuration knobs for [`JsonModemFacet`].
#[derive(Debug, Clone)]
pub struct JsonModemFacetOptions {
    partial_snapshots: bool,
    track_spans: bool,
    buffer: BufferOptions,
}

impl Default for JsonModemFacetOptions {
    fn default() -> Self {
        Self {
            partial_snapshots: true,
            track_spans: true,
            buffer: BufferOptions::default(),
        }
    }
}

impl JsonModemFacetOptions {
    /// Construct an option set with default values.
    #[must_use]
    pub fn new() -> Self {
        Self {
            partial_snapshots: true,
            track_spans: true,
            buffer: BufferOptions::default(),
        }
    }

    /// Toggle partial snapshot emission.
    #[must_use]
    pub const fn with_partial_snapshots(mut self, enabled: bool) -> Self {
        self.partial_snapshots = enabled;
        self
    }

    /// Toggle span tracking (currently used for byte counters only).
    #[must_use]
    pub const fn with_span_tracking(mut self, enabled: bool) -> Self {
        self.track_spans = enabled;
        self
    }

    /// Override the buffering strategy.
    #[must_use]
    pub fn with_buffer_options(mut self, buffer: BufferOptions) -> Self {
        self.buffer = buffer;
        self
    }
}

/// Result alias for facet adapter operations.
pub type FacetResult<T> = Result<T, JsonModemFacetError>;

/// Errors surfaced by [`JsonModemFacet`].
#[derive(Debug)]
pub enum JsonModemFacetError {
    Parser(ParserError<StdBackend>),
    Buffer(<StdBackend as crate::context::EventCtx>::Error),
    Reflect(ReflectError),
    Deserialize(DeserError<'static>),
    Incomplete,
    SnapshotActive,
    Finished,
}

impl fmt::Display for JsonModemFacetError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Parser(err) => write!(f, "parser error: {err}"),
            Self::Buffer(err) => write!(f, "buffer error: {err}"),
            Self::Reflect(err) => write!(f, "facet reflection error: {err}"),
            Self::Deserialize(err) => write!(f, "facet deserialize error: {err}"),
            Self::Incomplete => write!(f, "JSON input incomplete"),
            Self::SnapshotActive => write!(f, "snapshot borrow already active"),
            Self::Finished => write!(f, "adapter already finished"),
        }
    }
}

#[cfg(feature = "std")]
impl std::error::Error for JsonModemFacetError {}

/// Borrowed view of the in-progress (or final) facet value.
pub struct FacetSnapshot<'a, T> {
    pub value: &'a T,
    pub bytes_consumed: usize,
    pub is_final: bool,
    _guard: SnapshotGuard<'a>,
}

struct SnapshotGuard<'a> {
    active: &'a Cell<bool>,
}

impl Drop for SnapshotGuard<'_> {
    fn drop(&mut self) {
        self.active.set(false);
    }
}

struct SnapshotState<T> {
    ptr: Cell<*mut T>,
    active: Cell<bool>,
    final_value: Option<Box<T>>,
}

impl<T> SnapshotState<T> {
    fn new(ptr: *mut T) -> Self {
        Self {
            ptr: Cell::new(ptr),
            active: Cell::new(false),
            final_value: None,
        }
    }

    fn promote_final(&mut self, mut boxed: Box<T>) {
        let ptr = boxed.as_mut() as *mut T;
        self.ptr.set(ptr);
        self.final_value = Some(boxed);
    }

    fn borrow(
        &self,
        bytes_consumed: usize,
        is_final: bool,
    ) -> Result<FacetSnapshot<'_, T>, JsonModemFacetError> {
        if self.active.replace(true) {
            return Err(JsonModemFacetError::SnapshotActive);
        }
        let value_ref = if let Some(ref boxed) = self.final_value {
            boxed.as_ref()
        } else {
            unsafe { &*self.ptr.get() }
        };
        Ok(FacetSnapshot {
            value: value_ref,
            bytes_consumed,
            is_final,
            _guard: SnapshotGuard {
                active: &self.active,
            },
        })
    }

    fn view(&self) -> &T {
        if let Some(ref boxed) = self.final_value {
            boxed.as_ref()
        } else {
            unsafe { &*self.ptr.get() }
        }
    }

    fn take_final(&mut self) -> Option<Box<T>> {
        self.final_value.take()
    }
}

struct OwnedOutcome {
    span: Span,
    outcome: Outcome<'static>,
}

impl OwnedOutcome {
    fn new(outcome: Outcome<'static>, span: Span) -> Self {
        Self { span, outcome }
    }

    fn scalar(span: Span, scalar: Scalar<'static>) -> Self {
        Self::new(Outcome::Scalar(scalar), span)
    }

    fn into_spanned(self) -> Spanned<Outcome<'static>> {
        Spanned {
            node: self.outcome,
            span: self.span,
        }
    }
}

struct OutcomeTranslator {
    last_path: Vec<PathItem>,
}

impl OutcomeTranslator {
    fn new() -> Self {
        Self {
            last_path: Vec::new(),
        }
    }

    fn push_event(
        &mut self,
        event: BufferedEvent<'_, &'_ Path, StdBackend>,
        span: Span,
        queue: &mut VecDeque<OwnedOutcome>,
    ) {
        self.emit_keys(event.path(), span, queue);

        match event {
            BufferedEvent::Null { .. } => queue.push_back(OwnedOutcome::scalar(span, Scalar::Null)),
            BufferedEvent::Boolean { value, .. } => {
                queue.push_back(OwnedOutcome::scalar(span, Scalar::Bool(value)));
            }
            BufferedEvent::Number { value, .. } => {
                queue.push_back(OwnedOutcome::scalar(span, number_to_scalar(value)));
            }
            BufferedEvent::String {
                value,
                fragment,
                is_final,
                ..
            } => {
                if is_final {
                    let owned = value.map_or_else(|| fragment.into_owned(), Cow::into_owned);
                    queue.push_back(OwnedOutcome::scalar(
                        span,
                        Scalar::String(Cow::Owned(owned)),
                    ));
                }
            }
            BufferedEvent::ArrayBegin { .. } => {
                queue.push_back(OwnedOutcome::new(Outcome::ListStarted, span));
            }
            BufferedEvent::ArrayEnd { .. } => {
                queue.push_back(OwnedOutcome::new(Outcome::ListEnded, span));
            }
            BufferedEvent::ObjectBegin { .. } => {
                queue.push_back(OwnedOutcome::new(Outcome::ObjectStarted, span));
            }
            BufferedEvent::ObjectEnd { .. } => {
                queue.push_back(OwnedOutcome::new(Outcome::ObjectEnded, span));
            }
        }
    }

    fn emit_keys(&mut self, path: &[PathItem], span: Span, queue: &mut VecDeque<OwnedOutcome>) {
        let mut common = 0usize;
        while common < self.last_path.len()
            && common < path.len()
            && self.last_path[common] == path[common]
        {
            common += 1;
        }

        self.last_path.truncate(common);

        for item in path.iter().skip(common) {
            self.last_path.push(item.clone());
            if let PathItem::Key(key) = item {
                queue.push_back(OwnedOutcome::scalar(
                    span,
                    Scalar::String(Cow::Owned(key.to_string())),
                ));
            }
        }
    }
}

struct SpanTracker {
    enabled: bool,
    consumed: usize,
}

impl SpanTracker {
    fn new(enabled: bool) -> Self {
        Self {
            enabled,
            consumed: 0,
        }
    }

    fn start_chunk(&mut self, len: usize) -> ChunkSpans {
        let base = self.consumed;
        self.consumed = self.consumed.saturating_add(len);
        ChunkSpans {
            enabled: self.enabled,
            base,
            index: 0,
        }
    }

    fn total(&self) -> usize {
        self.consumed
    }

    fn is_enabled(&self) -> bool {
        self.enabled
    }
}

struct ChunkSpans {
    enabled: bool,
    base: usize,
    index: usize,
}

impl ChunkSpans {
    fn next(&mut self) -> Span {
        if self.enabled {
            let span = Span::new(self.base + self.index, 0);
            self.index = self.index.saturating_add(1);
            span
        } else {
            Span::new(0, 0)
        }
    }
}

struct FacetRunner<T>
where
    T: Facet<'static> + Default,
{
    wip: Option<Partial<'static>>,
    runner: StackRunner<'static>,
    snapshot: SnapshotState<T>,
    complete: bool,
}

impl<T> FacetRunner<T>
where
    T: Facet<'static> + Default,
{
    fn new() -> Result<Self, JsonModemFacetError> {
        let mut partial = Partial::alloc_shape(T::SHAPE).map_err(JsonModemFacetError::Reflect)?;
        let mut ptr: Option<*mut T> = None;
        unsafe {
            partial
                .set_from_function(|loc| {
                    let placed = loc.put(T::default());
                    ptr = Some(placed.as_mut_byte_ptr().cast::<T>());
                    Ok(())
                })
                .map_err(JsonModemFacetError::Reflect)?;
        }
        let ptr = ptr.expect("partial seeding produced pointer");
        let snapshot = SnapshotState::new(ptr);
        let runner = StackRunner {
            original_input: &[],
            input: &[],
            stack: vec![
                Instruction::Pop(PopReason::TopLevel),
                Instruction::Value(ValueReason::TopLevel),
            ],
            last_span: Span::new(0, 0),
            format_source: "jsonmodem",
            array_indices: Vec::new(),
            enum_tuple_field_count: None,
            enum_tuple_current_field: None,
        };
        Ok(Self {
            wip: Some(partial),
            runner,
            snapshot,
            complete: false,
        })
    }

    fn process_queue(
        &mut self,
        queue: &mut VecDeque<OwnedOutcome>,
    ) -> Result<(), DeserError<'static>> {
        while let Some(instruction) = self.runner.stack.last().copied() {
            match instruction {
                Instruction::Pop(reason) => {
                    self.runner.stack.pop();
                    let mut wip = self.wip.take().expect("partial available");
                    wip = self.runner.pop(wip, reason)?;
                    if reason == PopReason::TopLevel {
                        while wip.frame_count() > 1 {
                            wip.end().map_err(|err| deser_reflect(&self.runner, err))?;
                        }
                        let heap = wip
                            .build()
                            .map_err(|err| deser_reflect(&self.runner, err))?;
                        let value = heap
                            .materialize::<T>()
                            .map_err(|err| deser_reflect(&self.runner, err))?;
                        self.snapshot.promote_final(Box::new(value));
                        self.complete = true;
                    } else {
                        wip.end().map_err(|err| deser_reflect(&self.runner, err))?;
                        self.wip = Some(wip);
                    }
                    if reason == PopReason::TopLevel {
                        self.wip = None;
                        break;
                    }
                }
                Instruction::Value(_) => {
                    let Some(outcome) = queue.pop_front() else {
                        break;
                    };
                    self.runner.stack.pop();
                    let mut wip = self.wip.take().expect("partial available");
                    let span = outcome.span;
                    self.runner.last_span = span;
                    wip = self.runner.value(wip, outcome.into_spanned())?;
                    self.wip = Some(wip);
                }
                Instruction::ObjectKeyOrObjectClose => {
                    let Some(outcome) = queue.pop_front() else {
                        break;
                    };
                    self.runner.stack.pop();
                    let mut wip = self.wip.take().expect("partial available");
                    let span = outcome.span;
                    self.runner.last_span = span;
                    wip = self
                        .runner
                        .object_key_or_object_close(wip, outcome.into_spanned())?;
                    self.wip = Some(wip);
                }
                Instruction::ListItemOrListClose => {
                    let Some(outcome) = queue.pop_front() else {
                        break;
                    };
                    self.runner.stack.pop();
                    let mut wip = self.wip.take().expect("partial available");
                    let span = outcome.span;
                    self.runner.last_span = span;
                    wip = self
                        .runner
                        .list_item_or_list_close(wip, outcome.into_spanned())?;
                    self.wip = Some(wip);
                }
                Instruction::SkipValue => {
                    if let Some(span) = drain_value(queue) {
                        self.runner.stack.pop();
                        self.runner.last_span = span;
                    } else {
                        break;
                    }
                }
            }
        }
        Ok(())
    }

    fn snapshot(
        &self,
        bytes_consumed: usize,
        is_final: bool,
    ) -> Result<Option<FacetSnapshot<'_, T>>, JsonModemFacetError> {
        self.snapshot
            .borrow(bytes_consumed, self.complete || is_final)
            .map(Some)
    }

    fn finalize(mut self) -> Result<T, JsonModemFacetError> {
        if let Some(boxed) = self.snapshot.take_final() {
            Ok(*boxed)
        } else {
            Err(JsonModemFacetError::Incomplete)
        }
    }

    fn is_complete(&self) -> bool {
        self.complete
    }

    fn view(&self) -> &T {
        self.snapshot.view()
    }
}

fn drain_value(queue: &mut VecDeque<OwnedOutcome>) -> Option<Span> {
    let mut depth = 0usize;
    let mut complete_at = None;
    let mut last_span = None;

    for (idx, outcome) in queue.iter().enumerate() {
        last_span = Some(outcome.span);
        match outcome.outcome {
            Outcome::Scalar(_) => {
                if depth == 0 {
                    complete_at = Some(idx + 1);
                    break;
                }
            }
            Outcome::ListStarted | Outcome::ObjectStarted => {
                depth = depth.saturating_add(1);
            }
            Outcome::ListEnded | Outcome::ObjectEnded => {
                if depth == 0 {
                    complete_at = Some(idx + 1);
                    break;
                }
                depth = depth.saturating_sub(1);
                if depth == 0 {
                    complete_at = Some(idx + 1);
                    break;
                }
            }
        }
    }

    if depth == 0 {
        if let Some(count) = complete_at {
            for _ in 0..count {
                queue.pop_front();
            }
            last_span
        } else {
            None
        }
    } else {
        None
    }
}

fn map_buffer_error(err: BufferError<StdBackend>) -> JsonModemFacetError {
    match err {
        BufferError::Parser(e) => JsonModemFacetError::Parser(e),
        BufferError::Assembler(e) => JsonModemFacetError::Buffer(e),
    }
}

fn deser_reflect(runner: &StackRunner<'static>, err: ReflectError) -> DeserError<'static> {
    DeserError::new(
        DeserErrorKind::ReflectError(err),
        runner.original_input,
        runner.last_span,
    )
}

#[allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss,
    clippy::cast_possible_wrap
)]
fn number_to_scalar(value: f64) -> Scalar<'static> {
    if !value.is_finite() {
        return Scalar::String(Cow::Owned(value.to_string()));
    }

    let truncated = value.trunc();
    if (value - truncated).abs() <= f64::EPSILON {
        if value >= 0.0 && value <= u64::MAX as f64 {
            return Scalar::U64(truncated as u64);
        }
        if value >= i64::MIN as f64 && value <= i64::MAX as f64 {
            return Scalar::I64(truncated as i64);
        }

        return Scalar::String(Cow::Owned(truncated.to_string()));
    }
    Scalar::F64(value)
}

/// Streaming facet adapter built on top of [`JsonModemBuffers`].
pub struct JsonModemFacet<T>
where
    T: Facet<'static> + Default,
{
    parser_options: ParserOptions,
    buffers: JsonModemBuffers<StdBackend, StdValueAssembler>,
    runner: FacetRunner<T>,
    translator: OutcomeTranslator,
    pending: VecDeque<OwnedOutcome>,
    options: JsonModemFacetOptions,
    span_tracker: SpanTracker,
    finished: bool,
}

impl<T> JsonModemFacet<T>
where
    T: Facet<'static> + Default,
{
    /// Construct a new facet adapter with default emission options.
    ///
    /// # Errors
    ///
    /// Returns [`JsonModemFacetError::Reflect`] if the facet reflection layer
    /// cannot allocate or seed the backing partial value.
    pub fn new(options: ParserOptions) -> Result<Self, JsonModemFacetError> {
        Self::with_options(options, JsonModemFacetOptions::default())
    }

    /// Construct a facet adapter with explicit options.
    ///
    /// # Errors
    ///
    /// Returns [`JsonModemFacetError::Reflect`] if the facet reflection layer
    /// cannot allocate or seed the backing partial value.
    pub fn with_options(
        options: ParserOptions,
        opts: JsonModemFacetOptions,
    ) -> Result<Self, JsonModemFacetError> {
        let parser_options = options.with_allow_multiple_json_values(true);
        let buffers = JsonModemBuffers::new(parser_options, opts.buffer);
        let runner = FacetRunner::new()?;
        let track_spans = opts.track_spans;
        Ok(Self {
            parser_options,
            buffers,
            runner,
            translator: OutcomeTranslator::new(),
            pending: VecDeque::new(),
            options: opts,
            span_tracker: SpanTracker::new(track_spans),
            finished: false,
        })
    }

    /// Feed a chunk of UTF-8 and optionally receive an inline snapshot.
    ///
    /// # Errors
    ///
    /// Returns [`JsonModemFacetError::Parser`] or
    /// [`JsonModemFacetError::Buffer`] if the underlying streaming parser
    /// rejects the input, and [`JsonModemFacetError::Deserialize`]
    /// if the facet runner encounters structural mismatches while applying the
    /// chunk.
    pub fn feed(
        &mut self,
        chunk: &str,
    ) -> Result<Option<FacetSnapshot<'_, T>>, JsonModemFacetError> {
        if self.finished {
            return Err(JsonModemFacetError::Finished);
        }

        let mut spans = self.span_tracker.start_chunk(chunk.len());
        let mut events = self.buffers.feed(chunk);
        let translator = &mut self.translator;
        let runner = &mut self.runner;
        let pending = &mut self.pending;
        Self::drive_open(&mut events, &mut spans, translator, runner, pending)?;

        if self.options.partial_snapshots {
            let bytes = self.span_tracker.total();
            self.runner.snapshot(bytes, false)
        } else {
            Ok(None)
        }
    }

    /// Finalize the stream and return the owned facet value.
    ///
    /// # Errors
    ///
    /// Returns [`JsonModemFacetError::Parser`] or
    /// [`JsonModemFacetError::Buffer`] if the buffered parser sees invalid
    /// trailing data, [`JsonModemFacetError::Deserialize`] if the
    /// facet runner reports a structural violation, and
    /// [`JsonModemFacetError::Incomplete`] if the JSON stream finished
    /// before the facet value was fully materialized.
    pub fn finish(mut self) -> Result<T, JsonModemFacetError> {
        if self.finished {
            return Err(JsonModemFacetError::Finished);
        }

        let mut spans = self.span_tracker.start_chunk(0);
        let mut closed = self.buffers.finish();
        let translator = &mut self.translator;
        let runner = &mut self.runner;
        let pending = &mut self.pending;
        Self::drive_closed(&mut closed, &mut spans, translator, runner, pending)?;

        self.finished = true;
        if !self.runner.is_complete() {
            return Err(JsonModemFacetError::Incomplete);
        }
        self.runner.finalize()
    }

    /// View the current root without creating a new borrow guard.
    #[must_use]
    pub fn view(&self) -> &T {
        self.runner.view()
    }

    /// Reset the adapter back to its initial state while preserving options.
    ///
    /// # Errors
    ///
    /// Returns [`JsonModemFacetError::Reflect`] if the facet reflection layer
    /// cannot allocate or seed a fresh backing value during the reset.
    pub fn reset(&mut self) -> Result<(), JsonModemFacetError> {
        self.buffers = JsonModemBuffers::new(self.parser_options, self.options.buffer);
        self.runner = FacetRunner::new()?;
        self.translator = OutcomeTranslator::new();
        self.pending.clear();
        let enabled = self.span_tracker.is_enabled();
        self.span_tracker = SpanTracker::new(enabled);
        self.finished = false;
        Ok(())
    }

    fn drive_open(
        events: &mut BufferIter<'_>,
        spans: &mut ChunkSpans,
        translator: &mut OutcomeTranslator,
        runner: &mut FacetRunner<T>,
        pending: &mut VecDeque<OwnedOutcome>,
    ) -> Result<(), JsonModemFacetError> {
        while let Some(event) = events.next() {
            let event = event.map_err(map_buffer_error)?;
            let span = spans.next();
            translator.push_event(event, span, pending);
            runner
                .process_queue(pending)
                .map_err(JsonModemFacetError::Deserialize)?;
        }
        Ok(())
    }

    fn drive_closed(
        events: &mut BufferClosed,
        spans: &mut ChunkSpans,
        translator: &mut OutcomeTranslator,
        runner: &mut FacetRunner<T>,
        pending: &mut VecDeque<OwnedOutcome>,
    ) -> Result<(), JsonModemFacetError> {
        while let Some(event) = events.next() {
            let event = event.map_err(map_buffer_error)?;
            let span = spans.next();
            translator.push_event(event, span, pending);
            runner
                .process_queue(pending)
                .map_err(JsonModemFacetError::Deserialize)?;
        }
        Ok(())
    }
}
