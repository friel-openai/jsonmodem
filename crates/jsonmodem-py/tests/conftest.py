"""Select the portable public entry point for a separate full-suite run."""

import os


def pytest_configure():
    if os.environ.get("JSONMODEM_TEST_PORTABLE") == "1":
        import jsonmodem
        from jsonmodem import portable

        jsonmodem.dumps = portable.dumps
