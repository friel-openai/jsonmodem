"""Verify and load the public documents listed in public_corpus_manifest.json."""

import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import urllib.parse
import urllib.request


MANIFEST = Path(__file__).with_name("public_corpus_manifest.json")
NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def load_manifest(path=MANIFEST):
    manifest = json.loads(Path(path).read_bytes())
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("unsupported public corpus manifest version")
    if not isinstance(manifest.get("name"), str) or not NAME.fullmatch(manifest["name"]):
        raise ValueError("manifest must have a plain name without filesystem paths")
    documents = manifest.get("documents")
    if not isinstance(documents, list) or not documents:
        raise ValueError("manifest must contain at least one document")
    names, filenames = set(), set()
    for document in documents:
        if not isinstance(document, dict):
            raise ValueError("manifest documents must be objects")
        name = document.get("name", "")
        filename = document.get("filename", "")
        if not isinstance(name, str) or not NAME.fullmatch(name) or name in names:
            raise ValueError(f"invalid or duplicate document name: {name!r}")
        if filename != name + ".json" or filename in filenames:
            raise ValueError(f"invalid or duplicate filename for {name}")
        names.add(name)
        filenames.add(filename)
        size = document.get("size_bytes")
        if type(size) is not int or size < 1:
            raise ValueError(f"invalid size_bytes for {name}")
        digest = document.get("sha256", "")
        if not isinstance(digest, str) or not SHA256.fullmatch(digest):
            raise ValueError(f"invalid sha256 for {name}")
        if not isinstance(document.get("url"), str):
            raise ValueError(f"missing document URL for {name}")
        url = urllib.parse.urlsplit(document["url"])
        if url.scheme != "https" or not url.hostname or url.username is not None or url.fragment:
            raise ValueError(f"document URL must be an HTTPS URL without credentials: {name}")
        if document.get("terms") not in manifest.get("terms", {}):
            raise ValueError(f"missing data terms for {name}")
        if document.get("suite") not in manifest.get("suites", {}):
            raise ValueError(f"missing upstream suite for {name}")
    return manifest


def select_documents(manifest, names=None):
    documents = manifest["documents"]
    if names is None:
        return documents
    unknown = set(names) - {document["name"] for document in documents}
    if unknown:
        raise ValueError(f"unknown corpus cases: {sorted(unknown)}")
    if not names:
        raise ValueError("select at least one corpus case")
    return [document for document in documents if document["name"] in names]


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_document(document, directory):
    path = Path(directory) / document["filename"]
    if path.is_symlink():
        raise ValueError(f"corpus document must not be a symlink: {document['name']}")
    size = document["size_bytes"]
    with path.open("rb") as source:
        if os.fstat(source.fileno()).st_size != size:
            raise ValueError(f"size mismatch for {document['name']}")
        raw = source.read(size + 1)
    if len(raw) != size:
        raise ValueError(f"size mismatch for {document['name']}")
    if hashlib.sha256(raw).hexdigest() != document["sha256"]:
        raise ValueError(f"SHA-256 mismatch for {document['name']}")
    return raw


def fetch_document(document, directory, timeout=60):
    """Install a verified download atomically; leave an existing bad file intact."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / document["filename"]
    if destination.exists() or destination.is_symlink():
        read_document(document, directory)
        return "cached"
    request = urllib.request.Request(
        document["url"], headers={"User-Agent": "jsonmodem-public-corpus/1"}
    )
    temporary = None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if urllib.parse.urlsplit(response.geturl()).scheme != "https":
                raise ValueError("refusing a corpus download redirected away from HTTPS")
            with tempfile.NamedTemporaryFile(
                dir=directory, prefix="." + document["name"] + "-", suffix=".part", delete=False
            ) as target:
                temporary = Path(target.name)
                digest = hashlib.sha256()
                count = 0
                while True:
                    chunk = response.read(min(1 << 20, document["size_bytes"] - count + 1))
                    if not chunk:
                        break
                    count += len(chunk)
                    if count > document["size_bytes"]:
                        raise ValueError(f"size mismatch for {document['name']}")
                    digest.update(chunk)
                    target.write(chunk)
                if count != document["size_bytes"]:
                    raise ValueError(f"size mismatch for {document['name']}")
                if digest.hexdigest() != document["sha256"]:
                    raise ValueError(f"SHA-256 mismatch for {document['name']}")
        os.replace(temporary, destination)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return "downloaded"


def reject_constant(value):
    raise ValueError(f"non-JSON numeric constant: {value}")


def prepare_document(document, directory):
    """Build identical ordinary Python values without using a measured library."""
    raw = read_document(document, directory)
    value = json.loads(raw.decode("utf-8"), parse_constant=reject_constant)
    return raw, value


def assert_same(actual, expected):
    """Check full materialization, exact types, key order, and float bits."""
    pending = [iter(((actual, expected),))]
    while pending:
        pair = next(pending[-1], None)
        if pair is None:
            pending.pop()
            continue
        actual, expected = pair
        kind = type(expected)
        if type(actual) is not kind:
            raise AssertionError(f"value type differs: {type(actual).__name__} != {kind.__name__}")
        if kind is dict:
            if len(actual) != len(expected) or any(
                type(left) is not str or left != right
                for left, right in zip(actual, expected)
            ):
                raise AssertionError("dictionary keys or key order differ")
            pending.append(zip(actual.values(), expected.values()))
        elif kind is list:
            if len(actual) != len(expected):
                raise AssertionError("array lengths differ")
            pending.append(zip(actual, expected))
        elif kind is float:
            if not math.isfinite(expected) or actual.hex() != expected.hex():
                raise AssertionError("floating-point values differ or are nonfinite")
        elif kind in (str, int, bool, type(None)):
            if actual != expected:
                raise AssertionError("scalar values differ")
        else:
            raise AssertionError(f"not an ordinary JSON value: {kind.__name__}")
