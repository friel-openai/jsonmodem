#![cfg(not(any(PyPy, GraalPy)))]

use std::sync::{
    Arc,
    atomic::{AtomicUsize, Ordering},
};

use pyo3::{prelude::*, types::PyTupleMethods};

use crate::tuple_from_owned_items;

/// Observe when the last Python reference to a prepared tuple element is
/// dropped.
#[pyclass]
struct TupleOwner {
    index: usize,
    drops: Arc<AtomicUsize>,
}

impl Drop for TupleOwner {
    fn drop(&mut self) {
        self.drops.fetch_add(1, Ordering::Relaxed);
    }
}

#[test]
fn tuple_slots_transfer_inline_and_spilled_owners() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        // Cover empty tuples, the SmallVec inline boundary, and heap-backed owners.
        for length in [0, 1, 8, 9, 37] {
            let drops = Arc::new(AtomicUsize::new(0));
            let mut items = smallvec::SmallVec::new();
            for index in 0..length {
                items.push(
                    Py::new(
                        py,
                        TupleOwner {
                            index,
                            drops: drops.clone(),
                        },
                    )?
                    .into_bound(py)
                    .into_any(),
                );
            }
            let tuple = tuple_from_owned_items(py, items)?;
            assert_eq!(tuple.len(), length);
            for index in 0..length {
                let item = tuple.get_item(index)?;
                let owner = item.extract::<PyRef<'_, TupleOwner>>()?;
                assert_eq!(owner.index, index);
            }
            assert_eq!(drops.load(Ordering::Relaxed), 0);
            drop(tuple);
            assert_eq!(drops.load(Ordering::Relaxed), length);
        }
        Ok(())
    })
}

#[test]
fn tuple_slots_keep_one_reference_per_repeated_owner() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let drops = Arc::new(AtomicUsize::new(0));
        let owner = Py::new(
            py,
            TupleOwner {
                index: 7,
                drops: drops.clone(),
            },
        )?
        .into_bound(py)
        .into_any();
        let references = owner.get_refcnt();
        let items = (0..37).map(|_| owner.clone()).collect();
        let tuple = tuple_from_owned_items(py, items)?;
        assert_eq!(owner.get_refcnt(), references + 37);
        for item in tuple.iter() {
            assert!(item.is(&owner));
        }
        drop(owner);
        assert_eq!(drops.load(Ordering::Relaxed), 0);
        drop(tuple);
        assert_eq!(drops.load(Ordering::Relaxed), 1);
        Ok(())
    })
}

#[test]
fn tuple_slots_keep_elements_until_the_last_tuple_owner_drops() -> PyResult<()> {
    pyo3::prepare_freethreaded_python();
    Python::with_gil(|py| {
        let drops = Arc::new(AtomicUsize::new(0));
        let owner = Py::new(
            py,
            TupleOwner {
                index: 11,
                drops: drops.clone(),
            },
        )?
        .into_bound(py)
        .into_any();
        let tuple = tuple_from_owned_items(py, smallvec::smallvec![owner])?;
        let retained = tuple.clone();
        drop(tuple);
        assert_eq!(drops.load(Ordering::Relaxed), 0);
        {
            let item = retained.get_item(0)?;
            assert_eq!(item.extract::<PyRef<'_, TupleOwner>>()?.index, 11);
        }
        drop(retained);
        assert_eq!(drops.load(Ordering::Relaxed), 1);
        Ok(())
    })
}
