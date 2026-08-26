//! Callback-aware serialization retains every item before invoking Python.

use pyo3::{
    exceptions::PyTypeError,
    intern,
    prelude::*,
    types::{PyBytes, PyDict, PyInt, PyList, PyString, PyTuple, PyType},
};
use smallvec::SmallVec;

use super::{APPEND_NEWLINE, Encoder, INITIAL_OUTPUT_CAPACITY, MAX_ENCODE_DEPTH, SORT_KEYS};

const PASSTHROUGH_SUBCLASS: i32 = 256;
const PASSTHROUGH_DATACLASS: i32 = 2048;

/// Container snapshots keep their source alive for identity-based cycle checks.
struct Container<'py> {
    owner: Bound<'py, PyAny>,
    items: Items<'py>,
    count: usize,
    closing: u8,
}

/// Every remaining item is owned before attribute access or a default callback.
enum Items<'py> {
    Object(smallvec::IntoIter<[(Bound<'py, PyAny>, Bound<'py, PyAny>); 8]>),
    Array(std::vec::IntoIter<Bound<'py, PyAny>>),
}

/// Small objects retain their field owners without a heap allocation.
type ObjectItems<'py> = SmallVec<[(Bound<'py, PyAny>, Bound<'py, PyAny>); 8]>;

/// Uncommon Python operations share the native output buffer and depth counter.
struct ObjectEncoder<'py> {
    encoder: Encoder,
    default: Bound<'py, PyAny>,
    default_provided: bool,
    enum_type: Bound<'py, PyAny>,
    dataclass_fields: Bound<'py, PyAny>,
    key_text: Bound<'py, PyAny>,
    special: Bound<'py, PyAny>,
    datetime_types: [Bound<'py, PyAny>; 3],
    uuid_type: Bound<'py, PyAny>,
    str_base: Bound<'py, PyAny>,
    int_base: Bound<'py, PyAny>,
    get_attribute: Bound<'py, PyAny>,
    type_dict: Bound<'py, PyAny>,
    classes: SmallVec<[ClassAttributes<'py>; 4]>,
}

/// A live class dictionary view reflects changes made during callbacks.
struct ClassAttributes<'py> {
    owner: Bound<'py, PyType>,
    attributes: Bound<'py, PyAny>,
}

impl<'py> ObjectEncoder<'py> {
    fn new(
        default: Bound<'py, PyAny>,
        default_provided: bool,
        option: i32,
        helpers: &Bound<'py, PyTuple>,
    ) -> PyResult<Self> {
        Ok(Self {
            encoder: Encoder {
                output: Vec::with_capacity(INITIAL_OUTPUT_CAPACITY),
                option,
                base_depth: 0,
                dataclass_root: false,
                keys: Vec::new(),
            },
            default,
            default_provided,
            enum_type: helpers.get_item(0)?,
            dataclass_fields: helpers.get_item(1)?,
            key_text: helpers.get_item(2)?,
            special: helpers.get_item(3)?,
            datetime_types: [
                helpers.get_item(4)?,
                helpers.get_item(5)?,
                helpers.get_item(6)?,
            ],
            uuid_type: helpers.get_item(7)?,
            str_base: helpers.get_item(8)?,
            int_base: helpers.get_item(9)?,
            get_attribute: helpers.get_item(10)?,
            type_dict: helpers.get_item(11)?,
            classes: SmallVec::new(),
        })
    }

    fn class_attributes(&mut self, class: &Bound<'py, PyType>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(cached) = self.classes.iter().find(|cached| cached.owner.is(class)) {
            return Ok(cached.attributes.clone());
        }
        // The built-in descriptor bypasses custom metaclass attribute access.
        let attributes = self.type_dict.call1((class,))?;
        if self.classes.len() < 16 {
            self.classes.push(ClassAttributes {
                owner: class.clone(),
                attributes: attributes.clone(),
            });
        }
        Ok(attributes)
    }

    fn dict_items(&self, dict: &Bound<'py, PyDict>) -> PyResult<Items<'py>> {
        let mut items: ObjectItems<'py> = dict.iter().collect();
        for (key, _) in &mut items {
            if !key.is_exact_instance_of::<PyString>() {
                *key = self.key_text.call1((&*key, self.encoder.option))?;
            }
        }
        if self.encoder.option & SORT_KEYS != 0 {
            for (key, _) in &items {
                key.downcast::<PyString>()?
                    .to_str()
                    .map_err(|_| PyTypeError::new_err("str is not valid UTF-8"))?;
            }
            items.sort_by(|(left, _), (right, _)| {
                left.downcast::<PyString>()
                    .unwrap()
                    .to_str()
                    .unwrap()
                    .cmp(right.downcast::<PyString>().unwrap().to_str().unwrap())
            });
        }
        Ok(Items::Object(items.into_iter()))
    }

    fn dataclass_items(
        &self,
        value: &Bound<'py, PyAny>,
        class_attributes: &Bound<'py, PyAny>,
    ) -> PyResult<Items<'py>> {
        let py = value.py();
        let dict_name = intern!(py, "__dict__");
        let attributes = self.get_attribute.call1((value, dict_name, py.None()))?;
        let items =
            if !attributes.is_none() && !class_attributes.contains(intern!(py, "__slots__"))? {
                let attributes = attributes.downcast::<PyDict>()?;
                let mut items = ObjectItems::new();
                for (key, item) in attributes.iter() {
                    let text = key
                        .downcast::<PyString>()?
                        .to_str()
                        .map_err(|_| PyTypeError::new_err("str is not valid UTF-8"))?;
                    if !text.starts_with('_') {
                        items.push((key, item));
                    }
                }
                items
            } else {
                let fields = self.dataclass_fields.call1((value,))?;
                let fields = fields.downcast::<PyTuple>()?;
                let mut items = ObjectItems::new();
                for field in fields.iter() {
                    let name = field.getattr(intern!(py, "name"))?;
                    let text = name
                        .downcast::<PyString>()?
                        .to_str()
                        .map_err(|_| PyTypeError::new_err("str is not valid UTF-8"))?;
                    if !text.starts_with('_') {
                        let item = value.getattr(name.downcast::<PyString>()?)?;
                        items.push((name, item));
                    }
                }
                items
            };
        Ok(Items::Object(items.into_iter()))
    }

    fn default_value(&self, value: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let error = || -> PyResult<PyErr> {
            Ok(PyTypeError::new_err(format!(
                "Type is not JSON serializable: {}",
                value.get_type().name()?
            )))
        };
        if !self.default_provided {
            return Err(error()?);
        }
        match self.default.call1((value,)) {
            Ok(value) => Ok(value),
            Err(cause) => {
                let error = error()?;
                error.set_cause(value.py(), Some(cause));
                Err(error)
            }
        }
    }

    fn value(&mut self, value: Bound<'py, PyAny>) -> PyResult<()> {
        let py = value.py();
        let option = self.encoder.option;
        let mut value = value;
        let mut stack: SmallVec<[Container<'py>; 2]> = SmallVec::new();
        let mut default_depth = 0;
        loop {
            let depth = stack.len();
            let mut container = None;
            let mut limit = MAX_ENCODE_DEPTH;
            if self.encoder.scalar(&value)? {
                // Scalars include empty lists and tuples at any depth.
            } else if value
                .get_type()
                .mro()
                .iter()
                .any(|base| base.is(&self.enum_type))
            {
                value = value.getattr(intern!(py, "value"))?;
                continue;
            } else if option & PASSTHROUGH_SUBCLASS == 0 && value.is_instance_of::<PyString>() {
                value = self.str_base.call1((&value,))?;
                continue;
            } else if option & PASSTHROUGH_SUBCLASS == 0 && value.is_instance_of::<PyInt>() {
                value = self.int_base.call1((&value,))?;
                continue;
            } else if value.is_exact_instance_of::<PyTuple>() {
                container = Some(Items::Array(
                    value
                        .downcast::<PyTuple>()?
                        .iter()
                        .collect::<Vec<_>>()
                        .into_iter(),
                ));
            } else if (option & PASSTHROUGH_SUBCLASS == 0 || value.is_exact_instance_of::<PyList>())
                && value.is_instance_of::<PyList>()
            {
                container = Some(Items::Array(
                    value
                        .downcast::<PyList>()?
                        .iter()
                        .collect::<Vec<_>>()
                        .into_iter(),
                ));
            } else if (option & PASSTHROUGH_SUBCLASS == 0 || value.is_exact_instance_of::<PyDict>())
                && value.is_instance_of::<PyDict>()
            {
                container = Some(self.dict_items(value.downcast::<PyDict>()?)?);
            } else {
                let value_type = value.get_type();
                let datetime_or_uuid = self.datetime_types.iter().any(|kind| value_type.is(kind))
                    || value_type.is(&self.uuid_type);
                let attributes = self.class_attributes(&value_type)?;
                if !datetime_or_uuid
                    && attributes.contains(intern!(py, "__dataclass_fields__"))?
                    && !value.is_instance_of::<PyType>()
                    && option & PASSTHROUGH_DATACLASS == 0
                {
                    container = Some(self.dataclass_items(&value, &attributes)?);
                    limit += 1;
                } else {
                    let prepared =
                        self.special
                            .call1((&value, option, self.default_provided, depth))?;
                    if prepared.is_none() {
                        if default_depth == 255 {
                            return Err(PyTypeError::new_err(
                                "default serializer exceeds recursion limit",
                            ));
                        }
                        value = self.default_value(&value)?;
                        default_depth += 1;
                        continue;
                    }
                    let (encoded, replacement): (bool, Bound<'_, PyAny>) = prepared.extract()?;
                    if encoded {
                        self.encoder
                            .output
                            .extend_from_slice(replacement.downcast::<PyBytes>()?.as_bytes());
                    } else {
                        value = replacement;
                        continue;
                    }
                }
            }

            if let Some(items) = container {
                if depth >= limit || stack.iter().any(|frame| frame.owner.is(&value)) {
                    return Err(PyTypeError::new_err("Recursion limit reached"));
                }
                let (opening, closing) = match items {
                    Items::Object(_) => (b'{', b'}'),
                    Items::Array(_) => (b'[', b']'),
                };
                self.encoder.output.push(opening);
                stack.push(Container {
                    owner: value.clone(),
                    items,
                    count: 0,
                    closing,
                });
            }

            default_depth = 0;
            loop {
                let depth = stack.len();
                let Some(frame) = stack.last_mut() else {
                    return Ok(());
                };
                let item = match &mut frame.items {
                    Items::Object(items) => items.next().map(|(key, item)| (Some(key), item)),
                    Items::Array(items) => items.next().map(|item| (None, item)),
                };
                if let Some((key, item)) = item {
                    if frame.count != 0 {
                        self.encoder.output.push(b',');
                    }
                    frame.count += 1;
                    self.encoder.newline(depth);
                    if let Some(key) = key {
                        self.encoder.key(key.downcast::<PyString>()?)?;
                        self.encoder.output.push(b':');
                        if option & super::INDENT != 0 {
                            self.encoder.output.push(b' ');
                        }
                    }
                    value = item;
                    break;
                }
                let frame = stack.pop().expect("unfinished container");
                if frame.count != 0 {
                    self.encoder.newline(stack.len());
                }
                self.encoder.output.push(frame.closing);
            }
        }
    }
}

/// Continue through dataclasses and callbacks without restarting serialized
/// values.
#[pyfunction]
pub fn _dumps_objects(
    py: Python<'_>,
    obj: Bound<'_, PyAny>,
    default: Bound<'_, PyAny>,
    option: i32,
    default_provided: bool,
    helpers: Bound<'_, PyTuple>,
) -> PyResult<Py<PyBytes>> {
    let mut encoder = ObjectEncoder::new(default, default_provided, option, &helpers)?;
    encoder.value(obj)?;
    if option & APPEND_NEWLINE != 0 {
        encoder.encoder.output.push(b'\n');
    }
    Ok(PyBytes::new(py, &encoder.encoder.output).unbind())
}
