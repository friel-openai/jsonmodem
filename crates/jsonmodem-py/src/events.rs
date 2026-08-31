//! Event-only parsing with path tracking selected independently per instance.

use jsonmodem::{EventBackend, JsonModem, ParseEvent, lending_iterator::LendingIterator};
use pyo3::{
    prelude::*,
    types::{PyBool, PyTuple},
};

use crate::{
    EventRecord, EventRecordPool, InternedStrings, OwnedEventKind, PyEventIter, PyJsonModem,
    PyParserOptions, PyStringPayload, error_record, is_single_json_input, load_number,
    new_event_record_pool, read_parser_options, state_error, take_event_records, with_input_text,
};

/// Streams fragments without paths unless the caller enables path tracking.
#[pyclass(module = "jsonmodem._jsonmodem", name = "JsonModemEvents", unsendable)]
pub(crate) struct PyJsonModemEvents {
    parser: EventParser,
}

/// Select the implementation before collecting events, not once per token.
enum EventParser {
    Minimal(MinimalEvents),
    Tracked(PyJsonModem),
}

/// Retains parser state and reusable result storage, but no event paths.
struct MinimalEvents {
    parser: Option<JsonModem<EventBackend>>,
    finished: bool,
    interns: InternedStrings,
    record_pool: EventRecordPool,
}

#[pymethods]
impl PyJsonModemEvents {
    #[new]
    #[pyo3(signature=(options=None, *, track_paths=false))]
    fn new(py: Python<'_>, options: Option<Bound<'_, PyAny>>, track_paths: bool) -> PyResult<Self> {
        let parser = if track_paths {
            EventParser::Tracked(PyJsonModem::new(py, options, None, false)?)
        } else {
            let options = match options {
                Some(options) => read_parser_options(options)?,
                None => PyParserOptions::default(),
            };
            EventParser::Minimal(MinimalEvents {
                parser: Some(JsonModem::new(options.to_core())),
                finished: false,
                interns: InternedStrings::new(py)?,
                record_pool: new_event_record_pool(),
            })
        };
        Ok(Self { parser })
    }

    /// Parse a chunk or iterable of chunks into owned event tuples.
    /// Omitted paths are None, not the empty path used for the document root.
    fn feed(&mut self, py: Python<'_>, chunk_or_chunks: Bound<'_, PyAny>) -> PyResult<PyObject> {
        match &mut self.parser {
            EventParser::Tracked(parser) => parser.feed(py, chunk_or_chunks),
            EventParser::Minimal(parser) => parser.feed(py, chunk_or_chunks),
        }
    }

    /// Complete the stream and report unfinished tokens or containers.
    fn finish(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        match &mut self.parser {
            EventParser::Tracked(parser) => parser.finish(py),
            EventParser::Minimal(parser) => parser.finish(py),
        }
    }

    #[getter]
    fn is_finished(&self) -> bool {
        match &self.parser {
            EventParser::Tracked(parser) => parser.is_finished(),
            EventParser::Minimal(parser) => parser.finished,
        }
    }

    #[getter]
    fn track_paths(&self) -> bool {
        matches!(self.parser, EventParser::Tracked(_))
    }
}

impl MinimalEvents {
    fn feed(&mut self, py: Python<'_>, input: Bound<'_, PyAny>) -> PyResult<PyObject> {
        let parser = self
            .parser
            .as_mut()
            .ok_or_else(|| state_error("parser has already finished"))?;
        let mut records = take_event_records(&self.record_pool);
        if is_single_json_input(&input) {
            with_input_text(py, &input, "feed()", |chunk| {
                collect(py, parser, chunk, &self.interns, &mut records)
            })?;
        } else {
            for input in input.try_iter()? {
                with_input_text(py, &input?, "feed()", |chunk| {
                    collect(py, parser, chunk, &self.interns, &mut records)
                })?;
                if matches!(records.last(), Some(EventRecord::Error(_))) {
                    break;
                }
            }
        }
        Ok(PyEventIter::new(py, records, self.record_pool.clone())?.into_any())
    }

    fn finish(&mut self, py: Python<'_>) -> PyResult<PyObject> {
        if self.finished {
            return Err(state_error("finish() has already been called"));
        }
        let parser = self
            .parser
            .take()
            .ok_or_else(|| state_error("parser has already finished"))?;
        let mut records = take_event_records(&self.record_pool);
        let mut events = parser.finish();
        while let Some(event) = events.next() {
            match event {
                Ok(event) => records.push(record(py, event, &self.interns)?),
                Err(error) => {
                    records.push(error_record(
                        error.to_string(),
                        error.line(),
                        error.column(),
                    ));
                    break;
                }
            }
        }
        self.finished = true;
        Ok(PyEventIter::new(py, records, self.record_pool.clone())?.into_any())
    }
}

fn collect(
    py: Python<'_>,
    parser: &mut JsonModem<EventBackend>,
    mut chunk: &str,
    interns: &InternedStrings,
    records: &mut Vec<EventRecord>,
) -> PyResult<()> {
    loop {
        let mut produced = false;
        let mut events = parser.feed(chunk);
        while let Some(event) = events.next() {
            produced = true;
            match event {
                Ok(event) => records.push(record(py, event, interns)?),
                Err(error) => {
                    records.push(error_record(
                        error.to_string(),
                        error.line(),
                        error.column(),
                    ));
                    return Ok(());
                }
            }
        }
        drop(events);
        if chunk.is_empty() && !produced {
            return Ok(());
        }
        chunk = "";
    }
}

fn record(
    py: Python<'_>,
    event: ParseEvent<'_, &(), EventBackend>,
    interns: &InternedStrings,
) -> PyResult<EventRecord> {
    let (kind, payload) = match event {
        ParseEvent::Null { .. } => (OwnedEventKind::Null, py.None()),
        ParseEvent::Boolean { value, .. } => (
            OwnedEventKind::Bool,
            PyBool::new(py, value).to_owned().into_any().unbind(),
        ),
        ParseEvent::Number { value, .. } => (OwnedEventKind::Number, load_number(py, &value)?),
        ParseEvent::String {
            fragment,
            is_initial,
            is_final,
            ..
        } => (
            OwnedEventKind::String,
            Py::new(
                py,
                PyStringPayload {
                    fragment: fragment.as_ref().to_string(),
                    is_initial,
                    is_final,
                },
            )?
            .into_any(),
        ),
        ParseEvent::ArrayBegin { .. } => (OwnedEventKind::ArrayBegin, py.None()),
        ParseEvent::ArrayEnd { .. } => (OwnedEventKind::ArrayEnd, py.None()),
        ParseEvent::ObjectBegin { .. } => (OwnedEventKind::ObjectBegin, py.None()),
        ParseEvent::ObjectEnd { .. } => (OwnedEventKind::ObjectEnd, py.None()),
    };
    let kind = interns.kind_bound(py, kind).into_any().unbind();
    Ok(EventRecord::Event(
        PyTuple::new(py, [kind, py.None(), payload])?
            .into_any()
            .unbind(),
    ))
}
