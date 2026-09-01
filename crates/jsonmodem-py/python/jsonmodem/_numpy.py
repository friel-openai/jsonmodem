"""Optional NumPy support using immutable snapshots rather than Python value trees."""

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


def encode(value, option, default_provided, depth=0):
    if np is None:
        return None
    value_type = type(value)
    scalar = value_type in SCALAR_TYPES
    if value_type is not np.ndarray and not scalar:
        return None
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
