//! Exact numeric types own fixed metadata; scalar storage is copied per value.

#[cfg(all(
    Py_3_12,
    not(any(Py_3_13, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
    not(any(
        py_sys_config = "Py_DEBUG",
        py_sys_config = "Py_REF_DEBUG",
        py_sys_config = "Py_TRACE_REFS",
    )),
    target_os = "linux",
    target_arch = "x86_64",
    target_pointer_width = "64",
    target_endian = "little",
))]
mod root;

use pyo3::{
    exceptions::PyTypeError,
    gc::{PyTraverseError, PyVisit},
    intern,
    prelude::*,
    types::{PyCFunction, PyDict, PyModule, PyString, PyTuple, PyType},
};

use crate::{
    buffer::{self, BufferExport},
    text::string_text,
};

/// Values own their bits after the Python export has been released.
pub(crate) enum ScalarValue {
    Bool(bool),
    Signed(i64),
    Unsigned(u64),
    Float32(f32),
    Float64(f64),
}

/// Each variant fixes both the byte width and its interpretation.
#[derive(Clone, Copy)]
enum ScalarKind {
    Bool,
    I8,
    I16,
    I32,
    I64,
    U8,
    U16,
    U32,
    U64,
    F16,
    F32,
    F64,
}

impl ScalarKind {
    /// The export must belong to the exact immutable scalar admitted for this
    /// kind.
    unsafe fn read(self, export: &BufferExport<'_>) -> Option<ScalarValue> {
        // SAFETY: callers establish immutable scalar storage before
        // acquiring the export. Each copy still checks its descriptor and width.
        unsafe {
            match self {
                Self::Bool => export
                    .copy_immutable_array::<1>()
                    .map(|raw| ScalarValue::Bool(raw[0] == 1)),
                Self::I8 => export
                    .copy_immutable_array::<1>()
                    .map(|raw| ScalarValue::Signed(i8::from_ne_bytes(raw).into())),
                Self::I16 => export
                    .copy_immutable_array::<2>()
                    .map(|raw| ScalarValue::Signed(i16::from_ne_bytes(raw).into())),
                Self::I32 => export
                    .copy_immutable_array::<4>()
                    .map(|raw| ScalarValue::Signed(i32::from_ne_bytes(raw).into())),
                Self::I64 => export
                    .copy_immutable_array::<8>()
                    .map(|raw| ScalarValue::Signed(i64::from_ne_bytes(raw))),
                Self::U8 => export
                    .copy_immutable_array::<1>()
                    .map(|raw| ScalarValue::Unsigned(u8::from_ne_bytes(raw).into())),
                Self::U16 => export
                    .copy_immutable_array::<2>()
                    .map(|raw| ScalarValue::Unsigned(u16::from_ne_bytes(raw).into())),
                Self::U32 => export
                    .copy_immutable_array::<4>()
                    .map(|raw| ScalarValue::Unsigned(u32::from_ne_bytes(raw).into())),
                Self::U64 => export
                    .copy_immutable_array::<8>()
                    .map(|raw| ScalarValue::Unsigned(u64::from_ne_bytes(raw))),
                Self::F16 => export.copy_immutable_array::<2>().map(|raw| {
                    ScalarValue::Float32(half::f16::from_bits(u16::from_ne_bytes(raw)).to_f32())
                }),
                Self::F32 => export
                    .copy_immutable_array::<4>()
                    .map(|raw| ScalarValue::Float32(f32::from_ne_bytes(raw))),
                Self::F64 => export
                    .copy_immutable_array::<8>()
                    .map(|raw| ScalarValue::Float64(f64::from_ne_bytes(raw))),
            }
        }
    }
}

/// The owner prevents a type address from being reused while its kind is
/// cached.
struct ScalarType {
    class: Py<PyType>,
    kind: ScalarKind,
}

/// The lazy NumPy module owns this table separately in each interpreter.
#[pyclass(module = "jsonmodem._jsonmodem", name = "_NumericScalarTypes", frozen)]
#[derive(Default)]
pub(crate) struct NumericScalarTypes {
    types: [Option<ScalarType>; 12],
    // Query names exist before any root attempt, including its first call.
    #[cfg(all(
        Py_3_12,
        not(any(Py_3_13, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
        not(any(
            py_sys_config = "Py_DEBUG",
            py_sys_config = "Py_REF_DEBUG",
            py_sys_config = "Py_TRACE_REFS",
        )),
        target_os = "linux",
        target_arch = "x86_64",
        target_pointer_width = "64",
        target_endian = "little",
    ))]
    root_queries: Option<[Py<PyString>; 6]>,
}

#[pymethods]
impl NumericScalarTypes {
    #[new]
    fn new(numpy: Bound<'_, PyAny>, scalar_types: Bound<'_, PyAny>) -> PyResult<Self> {
        let py = numpy.py();
        let mut table = Self::default();
        if cfg!(PyPy)
            || cfg!(GraalPy)
            || !numpy.is_exact_instance_of::<PyModule>()
            || !scalar_types.is_exact_instance_of::<PyTuple>()
        {
            return Ok(table);
        }
        let scalar_types = scalar_types.downcast::<PyTuple>()?;
        let immutable = |class: &Bound<'_, PyAny>| -> PyResult<bool> {
            Ok(class.is_exact_instance_of::<PyType>()
                && class.getattr(intern!(py, "__flags__"))?.extract::<u64>()? & (1 << 8) != 0
                && class.getattr(intern!(py, "__module__"))?.eq("numpy")?)
        };
        let generic = numpy.getattr(intern!(py, "generic"))?;
        if scalar_types.len() > 13
            || !immutable(&generic)?
            || !generic.getattr(intern!(py, "__name__"))?.eq("generic")?
            || !scalar_types
                .iter()
                .all(|class| class.is_exact_instance_of::<PyType>())
        {
            return Ok(table);
        }
        let mut index = 0;
        for class in scalar_types.iter() {
            if !immutable(&class)? {
                continue;
            }
            let class = class.downcast_into::<PyType>()?;
            let name = class.getattr(intern!(py, "__name__"))?;
            let name = name
                .downcast::<PyString>()
                .map_err(|_| PyTypeError::new_err("NumPy scalar type name must be str"))?;
            if !matches!(
                string_text(name)?,
                "bool"
                    | "bool_"
                    | "int8"
                    | "int16"
                    | "int32"
                    | "int64"
                    | "uint8"
                    | "uint16"
                    | "uint32"
                    | "uint64"
                    | "longlong"
                    | "ulonglong"
                    | "float16"
                    | "float32"
                    | "float64"
            ) || !class.is_subclass(&generic)?
            {
                continue;
            }
            let value = class.call0()?;
            if !value.get_type().is(&class) {
                continue;
            }
            let dtype = value.getattr(intern!(py, "dtype"))?;
            if !dtype.getattr(intern!(py, "type"))?.is(&class)
                || !dtype.getattr(intern!(py, "isnative"))?.is_truthy()?
            {
                continue;
            }
            let kind = dtype.getattr(intern!(py, "kind"))?;
            let width = dtype.getattr(intern!(py, "itemsize"))?.extract::<usize>()?;
            let kind = kind
                .downcast::<PyString>()
                .map_err(|_| PyTypeError::new_err("NumPy dtype kind must be str"))?;
            let kind = match (string_text(kind)?, width) {
                ("b", 1) => ScalarKind::Bool,
                ("i", 1) => ScalarKind::I8,
                ("i", 2) => ScalarKind::I16,
                ("i", 4) => ScalarKind::I32,
                ("i", 8) => ScalarKind::I64,
                ("u", 1) => ScalarKind::U8,
                ("u", 2) => ScalarKind::U16,
                ("u", 4) => ScalarKind::U32,
                ("u", 8) => ScalarKind::U64,
                ("f", 2) => ScalarKind::F16,
                ("f", 4) => ScalarKind::F32,
                ("f", 8) => ScalarKind::F64,
                _ => continue,
            };
            if index == table.types.len() {
                break;
            }
            table.types[index] = Some(ScalarType {
                class: class.unbind(),
                kind,
            });
            index += 1;
        }
        #[cfg(all(
            Py_3_12,
            not(any(Py_3_13, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
            not(any(
                py_sys_config = "Py_DEBUG",
                py_sys_config = "Py_REF_DEBUG",
                py_sys_config = "Py_TRACE_REFS",
            )),
            target_os = "linux",
            target_arch = "x86_64",
            target_pointer_width = "64",
            target_endian = "little",
        ))]
        if index != 0 {
            table.root_queries = Some(root::query_names(py)?);
        }
        Ok(table)
    }

    fn __traverse__(&self, visit: PyVisit<'_>) -> Result<(), PyTraverseError> {
        for scalar_type in self.types.iter().flatten() {
            visit.call(&scalar_type.class)?;
        }
        #[cfg(all(
            Py_3_12,
            not(any(Py_3_13, PyPy, GraalPy, Py_LIMITED_API, Py_GIL_DISABLED)),
            not(any(
                py_sys_config = "Py_DEBUG",
                py_sys_config = "Py_REF_DEBUG",
                py_sys_config = "Py_TRACE_REFS",
            )),
            target_os = "linux",
            target_arch = "x86_64",
            target_pointer_width = "64",
            target_endian = "little",
        ))]
        if let Some(queries) = &self.root_queries {
            for query in queries {
                visit.call(query)?;
            }
        }
        Ok(())
    }
}

impl NumericScalarTypes {
    pub(crate) fn read(
        &self,
        value: &Bound<'_, PyAny>,
        helpers: &Bound<'_, PyTuple>,
        special: &Bound<'_, PyAny>,
    ) -> PyResult<Option<ScalarValue>> {
        let class = value.get_type();
        let Some(metadata) = self
            .types
            .iter()
            .flatten()
            .find(|metadata| class.is(metadata.class.bind(value.py())))
        else {
            return Ok(None);
        };
        if !helpers_are_default(helpers, special)? {
            return Ok(None);
        }
        buffer::with_export(value, |export| {
            // SAFETY: value has the exact owned, admitted NumPy scalar type.
            // That type's immutable numeric storage cannot change during this
            // scoped copy. A readonly arbitrary exporter would not suffice.
            Ok(unsafe { metadata.kind.read(export) })
        })
        .map(Option::flatten)
    }
}

/// Recheck each value: a preceding Python callback can replace a helper.
fn helpers_are_default(helpers: &Bound<'_, PyTuple>, special: &Bound<'_, PyAny>) -> PyResult<bool> {
    if helpers.len() != 8 {
        return Ok(false);
    }
    let py = helpers.py();
    let modules = helpers.get_borrowed_item(0)?;
    let module = helpers.get_borrowed_item(1)?;
    let native = helpers.get_borrowed_item(2)?;
    let numpy = helpers.get_borrowed_item(3)?;
    let encode = helpers.get_borrowed_item(4)?;
    let default_special = helpers.get_borrowed_item(5)?;
    let native_dumps = helpers.get_borrowed_item(6)?;
    let scalar_types = helpers.get_borrowed_item(7)?;
    if !special.is(default_special)
        || !modules.is_exact_instance_of::<PyDict>()
        || !module.is_exact_instance_of::<PyModule>()
        || !native.is_exact_instance_of::<PyModule>()
        || !numpy.is_exact_instance_of::<PyModule>()
        || !native_dumps.is_exact_instance_of::<PyCFunction>()
        || !scalar_types.is_exact_instance_of::<PyTuple>()
    {
        return Ok(false);
    }
    #[cfg(not(Py_LIMITED_API))]
    if !encode.is_exact_instance_of::<pyo3::types::PyFunction>()
        || !default_special.is_exact_instance_of::<pyo3::types::PyFunction>()
    {
        return Ok(false);
    }
    let modules = modules.downcast::<PyDict>()?;
    let module_dict = module.downcast::<PyModule>()?.dict();
    let native_dict = native.downcast::<PyModule>()?.dict();
    Ok(modules
        .get_item(intern!(py, "jsonmodem._numpy"))?
        .is_some_and(|current| current.is(module))
        && module_dict
            .get_item(intern!(py, "encode"))?
            .is_some_and(|current| current.is(encode))
        && module_dict
            .get_item(intern!(py, "native"))?
            .is_some_and(|current| current.is(native))
        && native_dict
            .get_item(intern!(py, "_numpy_dumps"))?
            .is_some_and(|current| current.is(native_dumps))
        && module_dict
            .get_item(intern!(py, "SCALAR_TYPES"))?
            .is_some_and(|current| current.is(scalar_types))
        && module_dict
            .get_item(intern!(py, "np"))?
            .is_some_and(|current| current.is(numpy)))
}
