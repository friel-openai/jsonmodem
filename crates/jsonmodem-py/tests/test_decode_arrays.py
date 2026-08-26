"""Check array construction across inline and allocated storage sizes."""

import json

import pytest

import jsonmodem


@pytest.mark.parametrize("length", [0, 1, 7, 8, 9, 15, 16, 17, 63, 64, 65, 1000])
def test_array_storage_boundaries(length):
    values = [None, True, False, -123, 1.25, "text", {"k": 4}, [1, 2]]
    array = [values[index % len(values)] for index in range(length)]
    for document in (json.dumps(array), json.dumps({"data": array, "tail": [array]})):
        assert jsonmodem.loads(document) == json.loads(document)


@pytest.mark.parametrize("length", [7, 8, 9, 64, 1000])
def test_array_error_discards_partial_result(length):
    prefix = json.dumps([{"k": index} for index in range(length)]).encode()[:-1]
    for ending in (b",", b",]", b",null", b",{\"k\":", b",\"\\uD800\"]"):
        with pytest.raises(json.JSONDecodeError):
            jsonmodem.loads(prefix + ending)
    assert jsonmodem.loads(b"[1,2,3]") == [1, 2, 3]
