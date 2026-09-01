"""Optional NumPy support using immutable snapshots rather than Python value trees."""

import sys

from . import _jsonmodem as native

try:
    import numpy as np
except ImportError:
    np = None

SCALAR_TYPES = () if np is None else (
    np.bool_, np.int8, np.int16, np.int32, np.int64,
    np.uint8, np.uint16, np.uint32, np.uint64,
    np.float16, np.float32, np.float64, np.datetime64,
)


def _numeric_scalar_metadata():
    """Retain fixed storage metadata only for immutable built-in scalar types."""
    metadata = {}
    if np is None or sys.implementation.name != "cpython":
        return metadata
    for scalar_type in SCALAR_TYPES:
        # Py_TPFLAGS_IMMUTABLETYPE is absent on older Python versions, which
        # retain the per-value lookup. Custom metaclasses retain it as well.
        if type(scalar_type) is not type or not scalar_type.__flags__ & (1 << 8):
            continue
        if scalar_type.__module__ != "numpy" or scalar_type.__name__ not in (
                "bool", "bool_", "int8", "int16", "int32", "int64",
                "uint8", "uint16", "uint32", "uint64", "longlong", "ulonglong",
                "float16", "float32", "float64"):
            continue
        # np.dtype can be replaced independently of existing valid scalars.
        # Read storage metadata from an instance of the immutable type instead.
        value = scalar_type(0)
        if type(value) is not scalar_type:
            continue
        dtype = value.dtype
        if (dtype.type is scalar_type and dtype.isnative
                and dtype.kind in "biuf" and dtype.itemsize in (1, 2, 4, 8)):
            metadata[scalar_type] = (dtype.kind, dtype.itemsize)
    return metadata


_NUMERIC_SCALAR_METADATA = _numeric_scalar_metadata()


def encode(value, option, default_provided, depth=0):
    if np is None:
        return None
    value_type = type(value)
    scalar = value_type in SCALAR_TYPES
    if value_type is not np.ndarray and not scalar:
        return None
    if (scalar and type(value_type) is type
            and value_type in _NUMERIC_SCALAR_METADATA):
        metadata = _NUMERIC_SCALAR_METADATA[value_type]
        return native._numpy_dumps(memoryview(value).tobytes(), (),
                                   metadata[0], metadata[1], "", option, depth)
    if not scalar and not value.flags.c_contiguous:
        if default_provided:
            return None
        raise TypeError("numpy array is not C contiguous; use ndarray.tolist() in default")
    dtype = value.dtype
    if not dtype.isnative:
        raise TypeError("numpy array is not native-endianness")
    if not scalar and (not value.ndim or dtype.kind not in "biufM" or dtype.itemsize not in (1,2,4,8)):
        if default_provided:
            return None
        raise TypeError("unsupported datatype in numpy array")
    unit = ""
    if dtype.kind == "M":
        unit, multiplier = np.datetime_data(dtype)
        if multiplier != 1:
            raise TypeError("numpy.datetime64 unit multipliers are not supported")
    if scalar:
        # A custom metaclass can compare equal to SCALAR_TYPES. Preserve the
        # forced base method instead of invoking its instance's buffer hook.
        raw = (memoryview(value).tobytes() if type(value_type) is type
               else np.generic.tobytes(value))
    else:
        raw = np.ndarray.tobytes(value, order="C")
    return native._numpy_dumps(raw, () if scalar else value.shape,
                               dtype.kind, dtype.itemsize, unit, option, depth)


def _initialize_numeric_helpers():
    """Retain matching type-table inputs and helpers across constructor callbacks."""
    from . import _compat

    # Python's GC owns these cycles; the native table only retains scalar types.
    # The tuple order matches helpers_are_default in numpy/scalars.rs.
    helpers = (
        sys.modules, sys.modules[__name__], native, np, encode,
        *_compat._NUMPY_DEFAULT_HELPERS, SCALAR_TYPES,
    )
    table = helpers[2]._NumericScalarTypes(helpers[3], helpers[7])
    if table is not None:
        _compat._ENCODER_HELPERS = _compat._ENCODER_HELPERS[:12] + (
            table, helpers,
        )
    return table, helpers


_NATIVE_NUMERIC_TYPES = None
if np is not None:
    _NATIVE_NUMERIC_TYPES, _NUMERIC_HELPERS = _initialize_numeric_helpers()
