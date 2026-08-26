"""Run the public release tests without copying them into this repository."""

import argparse
from pathlib import Path
import subprocess
import sys

import jsonmodem
import pytest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkout", type=Path, help="Local ijl/orjson 3.11.9 checkout")
    args = parser.parse_args()
    revision = subprocess.check_output(
        ["git", "-C", str(args.checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != "705515d77b28429d0b7c30c3d781abe52e8a1e5a":
        parser.error("expected the orjson 3.11.9 release commit")
    sys.modules["orjson"] = jsonmodem
    # Keep jsonmodem's identity; these four assertions test package names/version.
    return pytest.main([
        "-q", str(args.checkout / "test"), "-k",
        "not test_version and not test_dumps_module_str "
        "and not test_loads_module_str and not test_fragment_repr",
    ])


if __name__ == "__main__":
    raise SystemExit(main())
