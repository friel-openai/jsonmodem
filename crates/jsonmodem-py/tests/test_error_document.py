"""Focused assertions for the optional error-document constructor experiment."""

import builtins
import json
import sys
import types

import jsonmodem
import pytest


DOCUMENTS = [
    "",
    "!",
    "!!",
    "!" + "a" * 1022,
    "!" + "a" * 1023,
    "!" + "a" * 1024,
    "!" + "a" * 65535,
    "!" + "a" * 4095 + "\x00",
    "!" + "a" * 4095 + "\n",
    "!" + "a" * 4095 + "\u00e9",
    "!" + "a" * 4095 + "\u20ac",
    "!" + "a" * 4095 + "\U0001f642",
]


@pytest.mark.parametrize("document", DOCUMENTS, ids=range(len(DOCUMENTS)))
@pytest.mark.parametrize("kind", ["str", "bytes", "bytearray", "memoryview"])
def test_error_document_contents(document, kind):
    raw = document if kind == "str" else document.encode("utf-8")
    if kind == "bytearray":
        raw = bytearray(raw)
    elif kind == "memoryview":
        raw = memoryview(raw)
    with pytest.raises(jsonmodem.JSONDecodeError) as caught:
        jsonmodem.loads(raw)
    error = caught.value
    assert type(error.doc) is str
    assert error.doc == document
    assert type(error.msg) is str
    assert error.pos == 0
    assert error.lineno == 1
    assert error.colno == 1


@pytest.mark.parametrize("document", ["!", "!" * 4096, "!" + "\u00e9" * 4096])
def test_error_factory_arguments(monkeypatch, document):
    events = []
    original_import = builtins.__import__

    def import_module(name, *args, **kwargs):
        if name == "json":
            events.append("import")
        return original_import(name, *args, **kwargs)

    def factory(message, doc, position):
        events.append(("call", message, doc, position))
        assert type(message) is str
        assert type(doc) is str
        assert type(position) is int
        return json.JSONDecodeError(message, doc, position)

    replacement = types.ModuleType("json")

    def getattr_module(name):
        if name == "JSONDecodeError":
            events.append("getattr")
            return factory
        raise AttributeError(name)

    replacement.__getattr__ = getattr_module
    with monkeypatch.context() as patch:
        patch.setitem(sys.modules, "json", replacement)
        patch.setattr(builtins, "__import__", import_module)
        with pytest.raises(jsonmodem.JSONDecodeError) as caught:
            jsonmodem.loads(document)
    assert events[:2] == ["import", "getattr"]
    assert len(events) == 3
    assert events[2] == ("call", caught.value.msg, document, 0)


@pytest.mark.parametrize("stage", ["import", "getattr", "call"])
def test_error_factory_exception(monkeypatch, stage):
    sentinel = RuntimeError(stage)
    original_import = builtins.__import__

    def import_module(name, *args, **kwargs):
        if name == "json" and stage == "import":
            raise sentinel
        return original_import(name, *args, **kwargs)

    def factory(*args):
        raise sentinel

    replacement = types.ModuleType("json")

    def getattr_module(name):
        if name == "JSONDecodeError":
            if stage == "getattr":
                raise sentinel
            return factory
        raise AttributeError(name)

    replacement.__getattr__ = getattr_module
    with monkeypatch.context() as patch:
        patch.setitem(sys.modules, "json", replacement)
        patch.setattr(builtins, "__import__", import_module)
        with pytest.raises(RuntimeError) as caught:
            jsonmodem.loads("!" * 4096)
    assert caught.value is sentinel
