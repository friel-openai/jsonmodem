"""Omitting event paths must preserve parsing, payloads, and error behavior."""

import array

import pytest

import jsonmodem
from test_streaming_security import run_python


def normalized(parser, chunks):
    events = []
    try:
        for chunk in chunks:
            for kind, _path, payload in parser.feed(chunk):
                if kind == "string":
                    payload = payload.as_dict()
                events.append((kind, payload))
        for kind, _path, payload in parser.finish():
            if kind == "string":
                payload = payload.as_dict()
            events.append((kind, payload))
    except (jsonmodem.JsonModemSyntaxError, TypeError) as error:
        return events, (type(error).__name__, str(error))
    return events, None


@pytest.mark.parametrize("text", [
    '{"key":[{},[],true,false,null,"a\\nb\\uD83D\\uDE00",9007199254740993,18446744073709551615,-1.25e3]}',
    '{"\u00e9":"\U0001f600","\\u0061":2,"":0}',
    '0', '1e2', '[1,]', '{"bad\\q":null}', '{"bad\\ud800":null}',
    '[1e400]', '[123', '[\ntrue false]', '"unfinished',
])
@pytest.mark.parametrize("track_paths", [False, True])
def test_every_character_split_matches_existing_events(text, track_paths):
    for index in range(len(text) + 1):
        chunks = [text[:index], text[index:]]
        assert normalized(jsonmodem.JsonModemEvents(track_paths=track_paths), chunks) == normalized(jsonmodem.JsonModem(), chunks)
    assert normalized(jsonmodem.JsonModemEvents(track_paths=track_paths), list(text)) == normalized(jsonmodem.JsonModem(), list(text))


@pytest.mark.parametrize("mode", [jsonmodem.DecodeMode.StrictUnicode, jsonmodem.DecodeMode.ReplaceInvalid, jsonmodem.DecodeMode.SurrogatePreserving])
def test_multiple_roots_and_decode_modes(mode):
    options = jsonmodem.ParserOptions(allow_multiple=True, decode_mode=mode)
    chunks = ['{"key":"a', '\\ud800"}{}[[],{}] false 1e2']
    assert normalized(jsonmodem.JsonModemEvents(options), chunks) == normalized(jsonmodem.JsonModem(options), chunks)


@pytest.mark.parametrize("input_type", [bytes, bytearray, memoryview, lambda data: memoryview(array.array("B", data))])
def test_buffer_inputs_and_iterable_chunks(input_type):
    chunks = [input_type(b'{"key":"a'), input_type(b'b","integer":9007199254740993}')]
    minimal = jsonmodem.JsonModemEvents()
    events = list(minimal.feed(iter(chunks))) + list(minimal.finish())
    expected = list(jsonmodem.JsonModem().feed(chunks))
    assert [(kind, payload) for kind, _, payload in events] == [(kind, payload) for kind, _, payload in expected]
    assert all(path is None for _, path, _ in events)
    assert next(payload for kind, _, payload in events if kind == "number") == 9007199254740993


def test_instances_keep_independent_tracking_choices_and_owned_events():
    minimal = jsonmodem.JsonModemEvents()
    tracked = jsonmodem.JsonModemEvents(track_paths=True)
    first_minimal = minimal.feed('{"key":"first')
    first_tracked = tracked.feed('{"key":"first')
    list(minimal.feed(' second"}'))
    list(tracked.feed(' second"}'))
    list(minimal.finish())
    list(tracked.finish())
    left, right = list(first_minimal), list(first_tracked)
    assert [(kind, payload) for kind, _, payload in left] == [(kind, payload) for kind, _, payload in right]
    assert all(path is None for _, path, _ in left)
    assert right[0][1] == ()
    assert right[1][1] == (("key", "key"),)
    assert not minimal.track_paths and tracked.track_paths
    with pytest.raises(AttributeError):
        minimal.track_paths = True


@pytest.mark.parametrize("depth", [255, 256, 257])
def test_depth_limit_is_not_a_capability(depth):
    text = '[' * depth + '0' + ']' * depth
    actual = normalized(jsonmodem.JsonModemEvents(), [text])
    assert actual == normalized(jsonmodem.JsonModem(), [text])
    assert (actual[1] is not None) == (depth > 256)


def test_large_depth_is_rejected_before_eager_allocation():
    result = run_python('''
import os, resource, jsonmodem
if not os.environ.get("JSONMODEM_MEMORY_RUNNER"):
    resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
parser = jsonmodem.JsonModemEvents()
try:
    list(parser.feed("[" * 20000 + "0" + "]" * 20000))
except jsonmodem.JsonModemSyntaxError as error:
    assert "depth" in str(error)
else:
    raise AssertionError("deep input accepted")
''')
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("track_paths", [False, True])
def test_finish_and_invalid_input_contracts(track_paths):
    parser = jsonmodem.JsonModemEvents(track_paths=track_paths)
    assert not parser.is_finished
    assert list(parser.feed('1e2')) == []
    events = list(parser.finish())
    assert events[0][0] == "number" and events[0][2] == 100.0
    assert parser.is_finished
    with pytest.raises(jsonmodem.JsonModemStateError):
        parser.feed('0')
    with pytest.raises(jsonmodem.JsonModemStateError):
        parser.finish()
    with pytest.raises(TypeError, match="UTF-8"):
        jsonmodem.JsonModemEvents(track_paths=track_paths).feed(b'"\xff"')


def test_unavailable_output_modes_are_explicit():
    with pytest.raises(TypeError):
        jsonmodem.JsonModemEvents(paths="$.key")
    with pytest.raises(TypeError):
        jsonmodem.JsonModemEvents(byte_views=True)
