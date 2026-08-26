//! Callback-aware serialization retains every item before invoking Python.

use pyo3::{
    Borrowed,
    exceptions::PyTypeError,
    intern,
    prelude::*,
    types::{PyBytes, PyDict, PyInt, PyList, PyString, PyTuple, PyType},
};
use smallvec::SmallVec;

use super::{
    APPEND_NEWLINE, Encoder, INITIAL_OUTPUT_CAPACITY, MAX_ENCODE_DEPTH, SORT_KEYS, allocation_error,
};

const PASSTHROUGH_SUBCLASS: i32 = 256;
const PASSTHROUGH_DATACLASS: i32 = 2048;
const SERIALIZE_NUMPY: i32 = 16;

/// Container snapshots keep their source alive for identity-based cycle checks.
struct Container<'py> {
    owner: Bound<'py, PyAny>,
    items: Items<'py>,
    count: usize,
    closing: u8,
    // Callback replacements inherit this count; siblings restore it.
    default_depth: usize,
}

/// Every remaining item is owned before attribute access or a default callback.
enum Items<'py> {
    Object(smallvec::IntoIter<[(Bound<'py, PyAny>, Bound<'py, PyAny>); 8]>),
    Array(std::vec::IntoIter<Bound<'py, PyAny>>),
}

/// Small objects retain their field owners without a heap allocation.
type ObjectItems<'py> = SmallVec<[(Bound<'py, PyAny>, Bound<'py, PyAny>); 8]>;

#[inline]
fn push_field<'py>(
    items: &mut ObjectItems<'py>,
    key: Bound<'py, PyAny>,
    value: Bound<'py, PyAny>,
) -> PyResult<()> {
    items.try_reserve(1).map_err(|_| allocation_error())?;
    items.push((key, value));
    Ok(())
}

fn array_items<'py>(values: impl Iterator<Item = Bound<'py, PyAny>>) -> PyResult<Items<'py>> {
    let mut items = Vec::new();
    items
        .try_reserve(values.size_hint().0)
        .map_err(|_| allocation_error())?;
    for value in values {
        items.try_reserve(1).map_err(|_| allocation_error())?;
        items.push(value);
    }
    Ok(Items::Array(items.into_iter()))
}

/// Uncommon Python operations share the native output buffer and depth counter.
struct ObjectEncoder<'helpers, 'py> {
    encoder: Encoder<true>,
    default: Bound<'py, PyAny>,
    default_provided: bool,
    // The caller retains the immutable helper tuple until encoding finishes.
    enum_type: Borrowed<'helpers, 'py, PyAny>,
    dataclass_fields: Borrowed<'helpers, 'py, PyAny>,
    key_text: Borrowed<'helpers, 'py, PyAny>,
    special: Borrowed<'helpers, 'py, PyAny>,
    datetime_types: [Borrowed<'helpers, 'py, PyAny>; 3],
    uuid_type: Borrowed<'helpers, 'py, PyAny>,
    str_base: Borrowed<'helpers, 'py, PyAny>,
    int_base: Borrowed<'helpers, 'py, PyAny>,
    get_attribute: Borrowed<'helpers, 'py, PyAny>,
    type_dict: Borrowed<'helpers, 'py, PyAny>,
    classes: SmallVec<[ClassAttributes<'py>; 4]>,
}

/// A live class dictionary view reflects changes made during callbacks.
struct ClassAttributes<'py> {
    owner: Bound<'py, PyType>,
    attributes: Bound<'py, PyAny>,
}

impl<'helpers, 'py> ObjectEncoder<'helpers, 'py> {
    fn new(
        encoder: Encoder<true>,
        default: Bound<'py, PyAny>,
        default_provided: bool,
        helpers: &'helpers Bound<'py, PyTuple>,
    ) -> PyResult<Self> {
        Ok(Self {
            encoder,
            default,
            default_provided,
            enum_type: helpers.get_borrowed_item(0)?,
            dataclass_fields: helpers.get_borrowed_item(1)?,
            key_text: helpers.get_borrowed_item(2)?,
            special: helpers.get_borrowed_item(3)?,
            datetime_types: [
                helpers.get_borrowed_item(4)?,
                helpers.get_borrowed_item(5)?,
                helpers.get_borrowed_item(6)?,
            ],
            uuid_type: helpers.get_borrowed_item(7)?,
            str_base: helpers.get_borrowed_item(8)?,
            int_base: helpers.get_borrowed_item(9)?,
            get_attribute: helpers.get_borrowed_item(10)?,
            type_dict: helpers.get_borrowed_item(11)?,
            classes: SmallVec::new(),
        })
    }

    fn finish(mut self, py: Python<'py>, obj: Bound<'py, PyAny>) -> PyResult<Py<PyBytes>> {
        self.value(obj)?;
        if self.encoder.option & APPEND_NEWLINE != 0 {
            self.encoder.push(b'\n')?;
        }
        self.encoder.bytes(py)
    }

    fn class_attributes(&mut self, class: &Bound<'py, PyType>) -> PyResult<Bound<'py, PyAny>> {
        if let Some(cached) = self.classes.iter().find(|cached| cached.owner.is(class)) {
            return Ok(cached.attributes.clone());
        }
        // The built-in descriptor bypasses custom metaclass attribute access.
        let attributes = self.type_dict.call1((class,))?;
        if self.classes.len() < 16 {
            self.classes
                .try_reserve(1)
                .map_err(|_| allocation_error())?;
            self.classes.push(ClassAttributes {
                owner: class.clone(),
                attributes: attributes.clone(),
            });
        }
        Ok(attributes)
    }

    fn dict_items(&self, dict: &Bound<'py, PyDict>) -> PyResult<Items<'py>> {
        let mut items = ObjectItems::new();
        items
            .try_reserve(dict.len())
            .map_err(|_| allocation_error())?;
        for (key, value) in dict.iter() {
            push_field(&mut items, key, value)?;
        }
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
            // Original positions preserve equal converted keys without the
            // infallible scratch allocation used by slice::sort_by.
            let mut order: SmallVec<[usize; 16]> = SmallVec::new();
            order
                .try_reserve(items.len())
                .map_err(|_| allocation_error())?;
            order.extend(0..items.len());
            order.sort_unstable_by(|&left, &right| {
                items[left]
                    .0
                    .downcast::<PyString>()
                    .unwrap()
                    .to_str()
                    .unwrap()
                    .cmp(
                        items[right]
                            .0
                            .downcast::<PyString>()
                            .unwrap()
                            .to_str()
                            .unwrap(),
                    )
                    .then_with(|| left.cmp(&right))
            });
            for start in 0..order.len() {
                let mut position = start;
                while order[position] != start {
                    let next = order[position];
                    items.swap(position, next);
                    order[position] = position;
                    position = next;
                }
                order[position] = position;
            }
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
                        push_field(&mut items, key, item)?;
                    }
                }
                items
            } else {
                let fields = self.dataclass_fields.call1((value,))?;
                let fields = fields.downcast::<PyTuple>()?;
                let mut items = ObjectItems::new();
                for field in fields.iter_borrowed() {
                    let name = field.getattr(intern!(py, "name"))?;
                    let text = name
                        .downcast::<PyString>()?
                        .to_str()
                        .map_err(|_| PyTypeError::new_err("str is not valid UTF-8"))?;
                    if !text.starts_with('_') {
                        let item = value.getattr(name.downcast::<PyString>()?)?;
                        push_field(&mut items, name, item)?;
                    }
                }
                items
            };
        Ok(Items::Object(items.into_iter()))
    }

    fn default_value(&self, value: &Bound<'py, PyAny>) -> PyResult<Bound<'py, PyAny>> {
        let error = || -> PyResult<PyErr> {
            let py = value.py();
            // Class names can be large. Keep both message creation and exception
            // construction in fallible Python calls, without a Rust String copy.
            let message = intern!(py, "Type is not JSON serializable: ")
                .call_method1(intern!(py, "__add__"), (value.get_type().name()?,))?;
            let exception = py.get_type::<PyTypeError>().call1((message,))?;
            Ok(PyErr::from_value(exception))
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
                .iter_borrowed()
                .any(|base| base.is(self.enum_type))
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
                container = Some(array_items(value.downcast::<PyTuple>()?.iter())?);
            } else if (option & PASSTHROUGH_SUBCLASS == 0 || value.is_exact_instance_of::<PyList>())
                && value.is_instance_of::<PyList>()
            {
                let list = value.downcast::<PyList>()?;
                if list.is_empty() {
                    self.encoder.extend(b"[]")?;
                } else {
                    container = Some(array_items(list.iter())?);
                }
            } else if (option & PASSTHROUGH_SUBCLASS == 0 || value.is_exact_instance_of::<PyDict>())
                && value.is_instance_of::<PyDict>()
            {
                container = Some(self.dict_items(value.downcast::<PyDict>()?)?);
            } else {
                let value_type = value.get_type();
                let datetime_or_uuid = self.datetime_types.iter().any(|kind| value_type.is(kind))
                    || value_type.is(self.uuid_type);
                let attributes = self.class_attributes(&value_type)?;
                if !datetime_or_uuid
                    && attributes.contains(intern!(py, "__dataclass_fields__"))?
                    && !value.is_instance_of::<PyType>()
                    && option & PASSTHROUGH_DATACLASS == 0
                {
                    container = Some(self.dataclass_items(&value, &attributes)?);
                    limit += 1;
                } else {
                    let prepared = if datetime_or_uuid || option & SERIALIZE_NUMPY != 0 {
                        self.special
                            .call1((&value, option, self.default_provided, depth))?
                    } else {
                        py.None().into_bound(py)
                    };
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
                            .extend(replacement.downcast::<PyBytes>()?.as_bytes())?;
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
                self.encoder.push(opening)?;
                stack.try_reserve(1).map_err(|_| allocation_error())?;
                stack.push(Container {
                    owner: value,
                    items,
                    count: 0,
                    closing,
                    default_depth,
                });
            }

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
                    default_depth = frame.default_depth;
                    if frame.count != 0 {
                        self.encoder.push(b',')?;
                    }
                    frame.count += 1;
                    self.encoder.newline(depth)?;
                    if let Some(key) = key {
                        self.encoder.key(key.downcast::<PyString>()?)?;
                        self.encoder.push(b':')?;
                        if option & super::INDENT != 0 {
                            self.encoder.push(b' ')?;
                        }
                    }
                    value = item;
                    break;
                }
                let frame = stack.pop().expect("unfinished container");
                if frame.count != 0 {
                    self.encoder.newline(stack.len())?;
                }
                self.encoder.push(frame.closing)?;
            }
        }
    }
}

/// The first traversal cannot invoke callbacks, so its storage can be reused.
pub(super) fn dumps(
    py: Python<'_>,
    mut encoder: Encoder,
    obj: Bound<'_, PyAny>,
    default: Option<Bound<'_, PyAny>>,
) -> PyResult<PyObject> {
    encoder.output.clear();
    encoder.keys.clear();
    let helpers = py
        .import(intern!(py, "jsonmodem._compat"))?
        .getattr(intern!(py, "_ENCODER_HELPERS"))?;
    let default_provided = default.is_some();
    let default = default.unwrap_or_else(|| py.None().into_bound(py));
    Ok(ObjectEncoder::new(
        encoder.into_checked(),
        default,
        default_provided,
        helpers.downcast::<PyTuple>()?,
    )?
    .finish(py, obj)?
    .into_any())
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
    let mut encoder = Encoder {
        output: Vec::new(),
        option,
        base_depth: 0,
        dataclass_root: false,
        keys: Vec::new(),
    };
    encoder.reserve(INITIAL_OUTPUT_CAPACITY)?;
    ObjectEncoder::new(encoder, default, default_provided, &helpers)?.finish(py, obj)
}
