//! Root snapshots own exact numeric scalars and borrow their owned type
//! metadata.

use std::collections::TryReserveError;

use pyo3::{
    prelude::*,
    types::{PyBytes, PyString},
};

use super::{NumericScalarTypes, ScalarType, ScalarValue};
use crate::buffer;

/// These exact strings are created outside any callback-free serialization.
pub(super) fn query_names(py: Python<'_>) -> PyResult<[Py<PyString>; 6]> {
    fn name(py: Python<'_>, text: &str) -> PyResult<Py<PyString>> {
        // Unlike PyString::new/intern, both constructors report Python OOM.
        let bytes = PyBytes::new_with(py, text.len(), |output| {
            output.copy_from_slice(text.as_bytes());
            Ok(())
        })?;
        let name = PyString::from_object(bytes.as_any(), "utf-8", "strict")?;
        name.downcast_exact::<PyString>()?;
        Ok(name.unbind())
    }
    Ok([
        name(py, "jsonmodem._numpy")?,
        name(py, "encode")?,
        name(py, "native")?,
        name(py, "_numpy_dumps")?,
        name(py, "SCALAR_TYPES")?,
        name(py, "np")?,
    ])
}

/// The value and type table remain live through every scoped numeric copy.
pub(crate) struct RootScalar<'table, 'py> {
    value: Bound<'py, PyAny>,
    metadata: &'table ScalarType,
}

/// Owning both objects preserves insertion order and keeps snapshot drops
/// nonfinal while an unchanged source dictionary still owns them.
pub(crate) struct RootField<'table, 'py> {
    pub(crate) key: Bound<'py, PyString>,
    pub(crate) value: RootScalar<'table, 'py>,
}

impl RootScalar<'_, '_> {
    pub(crate) fn copy(&self) -> PyResult<Option<ScalarValue>> {
        buffer::with_export(&self.value, |export| {
            // SAFETY: root snapshots admit only this metadata's exact owned,
            // immutable NumPy numeric type. Each copy checks the descriptor and
            // fixed byte width. No view survives BufferExport's scoped release.
            Ok(unsafe { self.metadata.kind.read(export) })
        })
        .map(Option::flatten)
    }
}

impl NumericScalarTypes {
    /// Names cannot initialize or change during an attempted root write.
    pub(crate) fn root_query_names(&self) -> Option<&[Py<PyString>; 6]> {
        self.root_queries.as_ref()
    }

    /// Reject the whole sequence before copying any scalar or calling helpers.
    pub(crate) fn root_snapshot<'table, 'py>(
        &'table self,
        values: impl Iterator<Item = Bound<'py, PyAny>>,
    ) -> Result<Option<Vec<RootScalar<'table, 'py>>>, TryReserveError> {
        let mut snapshot = Vec::new();
        snapshot.try_reserve(values.size_hint().0)?;
        for value in values {
            let Some(metadata) = self
                .types
                .iter()
                .flatten()
                .find(|metadata| value.get_type_ptr() == metadata.class.as_ptr().cast())
            else {
                return Ok(None);
            };
            snapshot.try_reserve(1)?;
            snapshot.push(RootScalar { value, metadata });
        }
        Ok(Some(snapshot))
    }

    /// Check exact types without key conversion, equality, or helper calls.
    pub(crate) fn root_dict_snapshot<'table, 'py>(
        &'table self,
        fields: impl Iterator<Item = (Bound<'py, PyAny>, Bound<'py, PyAny>)>,
    ) -> Result<Option<Vec<RootField<'table, 'py>>>, TryReserveError> {
        let mut snapshot = Vec::new();
        snapshot.try_reserve(fields.size_hint().0)?;
        for (key, value) in fields {
            let Ok(key) = key.downcast_into_exact::<PyString>() else {
                return Ok(None);
            };
            let Some(metadata) = self
                .types
                .iter()
                .flatten()
                .find(|metadata| value.get_type_ptr() == metadata.class.as_ptr().cast())
            else {
                return Ok(None);
            };
            snapshot.try_reserve(1)?;
            snapshot.push(RootField {
                key,
                value: RootScalar { value, metadata },
            });
        }
        Ok(Some(snapshot))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    /// A declared impossible snapshot must fail before iteration starts.
    struct ImpossibleLength;

    impl Iterator for ImpossibleLength {
        type Item = Bound<'static, PyAny>;

        fn next(&mut self) -> Option<Self::Item> {
            panic!("snapshot allocation must fail before iteration")
        }

        fn size_hint(&self) -> (usize, Option<usize>) {
            (usize::MAX, Some(usize::MAX))
        }
    }

    #[test]
    fn root_snapshot_reports_impossible_reservation_without_iteration() {
        let types = NumericScalarTypes::default();
        assert!(types.root_snapshot(ImpossibleLength).is_err());
    }

    #[test]
    fn root_dict_snapshot_reports_impossible_reservation_without_iteration() {
        let types = NumericScalarTypes::default();
        assert!(
            types
                .root_dict_snapshot(ImpossibleLength.zip(ImpossibleLength))
                .is_err()
        );
    }
}
