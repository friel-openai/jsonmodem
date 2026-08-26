"""Binding regressions run without relying on the complete-document frontend."""

import subprocess
import sys

import pytest
import jsonmodem


@pytest.mark.parametrize("document,expected", [("0", 0), ("-0", 0), ("1e2", 100.0), ("1.25e2", 125.0), ("123456789", 123456789)])
def test_finish_finalizes_number(document, expected):
    parser = jsonmodem.JsonModem()
    events = list(parser.feed(document)) + list(parser.finish())
    assert [payload for kind, _, payload in events if kind == "number"] == [expected]


@pytest.mark.parametrize("name", ["JsonModem", "JsonModemValues"])
def test_depth_rejected_before_eager_allocation(name):
    code = f'''
import resource
import jsonmodem
resource.setrlimit(resource.RLIMIT_AS, (256 * 1024**2, 256 * 1024**2))
p = jsonmodem.{name}()
try:
    list(p.feed("[" * 20000 + "0" + "]" * 20000))
except jsonmodem.JsonModemSyntaxError as exc:
    assert "depth" in str(exc)
else:
    raise AssertionError("deep input accepted")
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("document", ["-", "1.", "1e", "1e+", "[1", '{"x":1'])
def test_finish_rejects_incomplete_number_or_container(document):
    parser = jsonmodem.JsonModem()
    with pytest.raises(jsonmodem.JsonModemSyntaxError):
        list(parser.feed(document))
        list(parser.finish())


@pytest.mark.parametrize("value", [9007199254740993, 18446744073709551615, -9223372036854775808])
def test_streaming_integers_are_exact(value):
    parser = jsonmodem.JsonModem()
    events = list(parser.feed(str(value) + " "))
    number = events[0][2]
    assert type(number) is int
    assert number == value


def test_streaming_rejects_infinity():
    parser = jsonmodem.JsonModem()
    with pytest.raises(jsonmodem.JsonModemSyntaxError):
        list(parser.feed("1e400 "))


@pytest.mark.parametrize("parser_type", [jsonmodem.JsonModem, jsonmodem.JsonModemValues])
def test_arbitrary_buffer_exporters_are_not_borrowed(parser_type):
    import array
    data = array.array("B", b"[1]")
    with pytest.raises(TypeError):
        list(parser_type().feed(memoryview(data)))


def test_document_copies_external_memoryview():
    import array
    backing = array.array("B", b"[1]")
    value = jsonmodem.loads(memoryview(backing))
    backing[1] = ord("2")
    assert value == [1]


@pytest.mark.parametrize("name", ["JsonModem", "JsonModemValues"])
def test_long_keys_are_shared_between_events(name):
    code = f'''
import resource
import jsonmodem
resource.setrlimit(resource.RLIMIT_AS, (128 * 1024**2, 128 * 1024**2))
doc = '{{"' + 'x' * 20000 + '":[' + ','.join(['0'] * 20000) + ']}}'
parser = jsonmodem.{name}()
events = list(parser.feed(doc))
list(parser.finish())
assert len(events) >= 20000
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("operation", ["loads", "dumps"])
def test_complete_documents_on_small_thread_stacks(operation):
    code = f'''
import resource, threading, jsonmodem
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
threading.stack_size(65536)
depth = 1024 if {operation!r} == 'loads' else 254
document = '[' * depth + '0' + ']' * depth
value = jsonmodem.loads(document)
results = []
def run():
    argument = document if {operation!r} == 'loads' else value
    results.append(jsonmodem.{operation}(argument))
thread = threading.Thread(target=run)
thread.start()
thread.join()
assert len(results) == 1
'''
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=10)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("number", ["0", "-0", "123456789", "9007199254740993", "18446744073709551615", "-123.456e-7"])
def test_every_numeric_chunk_split(number):
    import json
    expected = json.loads(number)
    for split in range(len(number) + 1):
        parser = jsonmodem.JsonModem()
        events = list(parser.feed(number[:split])) + list(parser.feed(number[split:]))
        events += list(parser.finish())
        numbers = [payload for kind, _, payload in events if kind == "number"]
        assert numbers == [expected], (number, split)
        assert type(numbers[0]) is type(expected)
        values = jsonmodem.JsonModemValues()
        list(values.feed([number[:split], number[split:]]))
        list(values.finish())
        snapshot = values.view().snapshot()
        assert snapshot == expected
        assert type(snapshot) is type(expected)


@pytest.mark.parametrize("document", ["1.e2", "[1.e2]", "-0.e+2"])
def test_fraction_requires_a_digit(document):
    for cls in (jsonmodem.JsonModem, jsonmodem.JsonModemValues):
        parser = cls()
        with pytest.raises(jsonmodem.JsonModemSyntaxError):
            list(parser.feed(document))
            list(parser.finish())


def test_byte_views_reject_multidimensional_input_and_bytes_subclasses():
    class Exporter(bytes):
        def __buffer__(self, flags):
            raise AssertionError("custom exporter must never be called")

    for data in (memoryview(b'["abcdef"]').cast('B', shape=(2, 5)), Exporter(b'0')):
        with pytest.raises(TypeError):
            list(jsonmodem.JsonModem(byte_views=True).feed(data))
