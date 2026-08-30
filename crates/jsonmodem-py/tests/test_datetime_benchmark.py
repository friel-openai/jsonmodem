"""Check deterministic datetime benchmark inputs without invoking a serializer."""

import datetime
import importlib.util
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import patch
import uuid


SOURCE = Path(__file__).resolve().parents[1] / "benchmarks" / "bench_datetime.py"
SPEC = importlib.util.spec_from_file_location("datetime_benchmark_fixtures", SOURCE)
benchmark = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = benchmark
SPEC.loader.exec_module(benchmark)


class DatetimeFixturesTests(unittest.TestCase):
    def setUp(self):
        self.cases = {name: (value, kwargs) for name, value, kwargs in benchmark.workloads()}

    def test_inventory_and_sizes(self):
        self.assertEqual(len(self.cases), 43)
        for name, value_type in (
            ("datetime_naive", datetime.datetime), ("datetime_utc", datetime.datetime),
            ("datetime_fixed_offset", datetime.datetime), ("date", datetime.date), ("time", datetime.time),
        ):
            self.assertIs(type(self.cases[name + "_scalar"][0]), value_type)
            for size in (16, 1024):
                value, kwargs = self.cases[f"{name}_{size}"]
                self.assertIs(type(value), list)
                self.assertEqual(len(value), size)
                self.assertTrue(all(type(item) is value_type for item in value))
                self.assertEqual(kwargs, {})

    def test_generated_values_are_repeatable(self):
        repeated = {name: (value, kwargs) for name, value, kwargs in benchmark.workloads()}
        self.assertEqual(list(self.cases), list(repeated))
        for name, (value, kwargs) in self.cases.items():
            other, other_kwargs = repeated[name]
            self.assertEqual(value, other, name)
            self.assertEqual(repr(value), repr(other), name)
            self.assertEqual(kwargs, other_kwargs, name)

    def test_microsecond_cases_do_not_modify_shared_inputs(self):
        for name in ("datetime_naive", "datetime_utc", "time"):
            nonzero = self.cases[name + "_1024"][0]
            zero = self.cases[name + "_1024_zero_microseconds"][0]
            self.assertTrue(all(item.microsecond != 0 for item in nonzero))
            self.assertTrue(all(item.microsecond == 0 for item in zero))
            self.assertTrue(all(left.replace(microsecond=0) == right for left, right in zip(nonzero, zero)))

    def test_all_naive_option_combinations(self):
        for suffix, flags in (
            ("naive_utc", 2), ("omit_microseconds", 8), ("utc_z", 128),
            ("naive_utc_omit_microseconds", 10), ("naive_utc_z", 130),
            ("omit_microseconds_utc_z", 136), ("naive_utc_omit_microseconds_utc_z", 138),
        ):
            values, kwargs = self.cases["datetime_naive_1024_" + suffix]
            self.assertIs(values, self.cases["datetime_naive_1024"][0])
            self.assertEqual(kwargs, {"option": flags})

    def test_timezone_controls_are_distinct(self):
        self.assertIsNone(self.cases["datetime_naive_scalar"][0].tzinfo)
        self.assertIs(self.cases["datetime_utc_scalar"][0].tzinfo, datetime.timezone.utc)
        named_zero = self.cases["datetime_named_zero_offset_1024"][0][0]
        self.assertIsNot(named_zero.tzinfo, datetime.timezone.utc)
        self.assertEqual(named_zero.utcoffset(), datetime.timedelta(0))
        self.assertEqual(self.cases["datetime_fixed_offset_scalar"][0].utcoffset(), datetime.timedelta(hours=5, minutes=30))
        self.assertEqual(self.cases["datetime_negative_offset_1024"][0][0].utcoffset(), datetime.timedelta(hours=-3, minutes=-30))
        self.assertEqual(self.cases["datetime_seconds_offset_1024"][0][0].utcoffset(), datetime.timedelta(hours=5, minutes=30, seconds=45))

    def test_callbacks_have_explicit_inputs_and_options(self):
        values, kwargs = self.cases["datetime_passthrough"]
        self.assertEqual(kwargs, {"option": 512, "default": benchmark.isoformat})
        self.assertIs(values, self.cases["datetime_naive_1024"][0])
        values, kwargs = self.cases["datetime_subclass"]
        self.assertEqual(kwargs, {"default": benchmark.isoformat})
        self.assertTrue(all(type(value) is benchmark.DateTimeSubclass for value in values))
        self.assertEqual(kwargs["default"](values[0]), "2001-01-02T03:04:05")

    def test_controls_keep_ordinary_types(self):
        self.assertIs(type(self.cases["uuid_scalar_control"][0]), uuid.UUID)
        self.assertTrue(all(type(value) is uuid.UUID for value in self.cases["uuid_list_control"][0]))
        self.assertEqual(self.cases["dict_control"][0], {"id": 123, "name": "record", "active": True})
        self.assertEqual(self.cases["list_control"][0], list(range(1024)))
        self.assertEqual(self.cases["string_control"][0], "ordinary text")
        self.assertTrue(all(type(value) is benchmark.Record and type(value.value) is str
                            for value in self.cases["dataclass_control"][0]))

    def test_reference_padding_difference_is_explicit(self):
        value = [datetime.time(9, 51, 51, microsecond) for microsecond in (1, 9999, 10000, 40974, 99999, 100000)]
        correct, reference = benchmark.time_padding_outputs(value)
        self.assertEqual(correct, b'["09:51:51.000001","09:51:51.009999","09:51:51.010000","09:51:51.040974","09:51:51.099999","09:51:51.100000"]')
        self.assertEqual(reference, b'["09:51:51.000001","09:51:51.009999","09:51:51.10000","09:51:51.40974","09:51:51.99999","09:51:51.100000"]')
        for name in benchmark.REFERENCE_TIME_PADDING_CASES:
            value, kwargs = self.cases[name]
            correct, reference = benchmark.time_padding_outputs(value)
            benchmark.check_outputs(name, value, kwargs, correct, reference, "3.11.9")
            metadata = benchmark.fixture_metadata(value, kwargs, correct, reference)
            self.assertFalse(metadata["reference_exact_match"])
            self.assertGreater(metadata["output_bytes"], metadata["reference_output_bytes"])

    def test_reference_exception_does_not_allow_other_differences(self):
        value, kwargs = self.cases["time_16"]
        correct, reference = benchmark.time_padding_outputs(value)
        for name, options, ours, theirs, version in (
            ("time_16", kwargs, b"[]", reference, "3.11.9"),
            ("time_16", kwargs, reference, reference, "3.11.9"),
            ("time_16", kwargs, correct, b"[]", "3.11.9"),
            ("time_16", kwargs, correct, reference, "3.12.0"),
            ("time_16", {"option": 8}, correct, reference, "3.11.9"),
            ("time_scalar", kwargs, correct, reference, "3.11.9"),
        ):
            with self.subTest(name=name, options=options, ours=ours, theirs=theirs, version=version):
                with self.assertRaises(AssertionError):
                    benchmark.check_outputs(name, value, options, ours, theirs, version)

    def test_helpers_load_without_changing_the_search_path(self):
        before = list(sys.path)
        native_modules = {name for name in sys.modules if name in ("orjson", "jsonmodem")}
        # The unchanged timer imports both libraries; this test checks imports, not serialization.
        with patch.dict(sys.modules, {name: ModuleType(name) for name in ("orjson", "jsonmodem")}):
            self.assertTrue(callable(benchmark._load_helper("bench_orjson_compat").measure))
            self.assertTrue(callable(benchmark._load_helper("bench_output_buffers").compare))
        self.assertEqual(sys.path, before)
        self.assertEqual({name for name in sys.modules if name in ("orjson", "jsonmodem")}, native_modules)


if __name__ == "__main__":
    unittest.main()
