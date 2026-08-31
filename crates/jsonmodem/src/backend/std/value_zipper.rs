#![allow(dead_code)]
#[cfg(feature = "cached-zipper")]
use alloc::boxed::Box;
use alloc::{collections::BTreeMap, sync::Arc, vec::Vec};
use core::cmp::Ordering;

use super::{StdPath, value::Value};
use crate::path::{Path, PathItem};

#[cfg(feature = "cached-zipper")]
#[allow(unsafe_code)]
mod cached;

#[derive(Debug)]
/// Owns a partial value tree and the current event's path.
/// The `cached-zipper` feature caches branch pointers instead of walking from
/// the root for each access. Both implementations expose the same borrows.
pub struct ValueZipper {
    // Boxing keeps the root address stable when cached pointers exist.
    #[cfg(feature = "cached-zipper")]
    root: Box<Value>,
    #[cfg(not(feature = "cached-zipper"))]
    root: Value,
    // Discard descendant pointers before replacing or growing an ancestor.
    #[cfg(feature = "cached-zipper")]
    path_nodes: Vec<core::ptr::NonNull<Value>>,
    // Keep Send/Sync unchanged when another dependency enables the cache.
    #[cfg(not(feature = "cached-zipper"))]
    thread_bound: core::marker::PhantomData<*mut Value>,
    path_components: Vec<PathItem>,
}

impl Default for ValueZipper {
    fn default() -> Self {
        Self::new()
    }
}

impl ValueZipper {
    #[inline]
    pub fn new() -> Self {
        Self {
            #[cfg(feature = "cached-zipper")]
            root: Box::new(Value::Null),
            #[cfg(not(feature = "cached-zipper"))]
            root: Value::Null,
            #[cfg(feature = "cached-zipper")]
            path_nodes: Vec::with_capacity(8),
            #[cfg(not(feature = "cached-zipper"))]
            thread_bound: core::marker::PhantomData,
            path_components: Vec::with_capacity(8),
        }
    }

    #[inline]
    pub fn insert_value(&mut self, path: &Path, value: Value) {
        let (_, slot) = self.align_path(path);
        *slot = value;
    }

    #[inline]
    pub fn take_root(&mut self) -> Value {
        #[cfg(feature = "cached-zipper")]
        self.path_nodes.clear();
        self.path_components.clear();
        #[cfg(feature = "cached-zipper")]
        let root = self.root.as_mut();
        #[cfg(not(feature = "cached-zipper"))]
        let root = &mut self.root;
        core::mem::replace(root, Value::Null)
    }

    #[inline]
    pub fn read_root(&self) -> &Value {
        &self.root
    }

    #[inline]
    pub(crate) fn with_leaf_mut<'a, F>(
        &'a mut self,
        path: &Path,
        mutate: F,
    ) -> (&'a StdPath, &'a Value)
    where
        F: FnOnce(&mut Value),
    {
        let (path, slot) = self.align_path(path);
        mutate(slot);
        (path, slot)
    }

    #[inline]
    pub(crate) fn with_leaf<'a>(&'a mut self, path: &Path) -> (&'a StdPath, &'a Value) {
        let (path, slot) = self.align_path(path);
        (path, slot)
    }

    #[cfg(not(feature = "cached-zipper"))]
    #[inline]
    fn align_path(&mut self, path: &Path) -> (&StdPath, &mut Value) {
        let shared = self
            .path_components
            .iter()
            .zip(path)
            .take_while(|(left, right)| left == right)
            .count();
        self.path_components.truncate(shared);
        self.path_components.extend_from_slice(&path[shared..]);
        let mut current = &mut self.root;
        for component in &self.path_components {
            current = descend_one(current, component);
        }
        (&self.path_components, current)
    }
}

#[inline]
fn ensure_array(value: &mut Value) -> &mut Vec<Value> {
    if !matches!(value, Value::Array(_)) {
        *value = Value::Array(Vec::new());
    }
    match value {
        Value::Array(values) => values,
        _ => unreachable!(),
    }
}

#[inline]
fn ensure_object(value: &mut Value) -> &mut BTreeMap<Arc<str>, Value> {
    if !matches!(value, Value::Object(_)) {
        *value = Value::Object(BTreeMap::new());
    }
    match value {
        Value::Object(map) => map,
        _ => unreachable!(),
    }
}

#[inline]
fn descend_one<'a>(current: &'a mut Value, component: &PathItem) -> &'a mut Value {
    match component {
        PathItem::Key(key) => ensure_object(current)
            .entry(key.clone())
            .or_insert(Value::Null),
        PathItem::Index(index) => {
            let array = ensure_array(current);
            let idx = *index;
            match idx.cmp(&array.len()) {
                Ordering::Less => {}
                Ordering::Equal => array.push(Value::Null),
                Ordering::Greater => array.resize(idx + 1, Value::Null),
            }
            array.get_mut(idx).expect("array resized to contain index")
        }
    }
}

#[cfg(test)]
mod tests {
    use alloc::{format, vec};

    use super::*;

    #[test]
    fn feature_preserves_send_and_sync_contract() {
        // If ValueZipper gains Send or Sync, the corresponding inferred
        // trait parameter becomes ambiguous and this test fails to compile.
        trait NotSend<A> {
            fn check() {}
        }
        impl<T: ?Sized> NotSend<()> for T {}
        impl<T: ?Sized + Send> NotSend<u8> for T {}

        trait NotSync<A> {
            fn check() {}
        }
        impl<T: ?Sized> NotSync<()> for T {}
        impl<T: ?Sized + Sync> NotSync<u8> for T {}

        let _ = <ValueZipper as NotSend<_>>::check;
        let _ = <ValueZipper as NotSync<_>>::check;
    }

    #[test]
    fn memory_safety_array_growth_and_root_reuse() {
        let mut zipper = ValueZipper::new();
        for round in 0..3 {
            zipper.insert_value(&vec![], Value::Array(Vec::new()));
            for index in 0..64 {
                let path = vec![PathItem::Index(index)];
                let (actual_path, value) = zipper.with_leaf_mut(&path, |value| {
                    *value = Value::Number(f64::from(u32::try_from(round + index).unwrap()));
                });
                assert_eq!(actual_path, &path);
                assert_eq!(
                    value,
                    &Value::Number(f64::from(u32::try_from(round + index).unwrap()))
                );
            }
            zipper.with_leaf(&vec![]);
            let expected = Value::Array(
                (0..64)
                    .map(|index| Value::Number(f64::from(u32::try_from(round + index).unwrap())))
                    .collect(),
            );
            assert_eq!(zipper.read_root(), &expected);
            assert_eq!(zipper.take_root(), expected);
            assert_eq!(zipper.read_root(), &Value::Null);
            assert!(zipper.path_components.is_empty());
        }
    }

    #[test]
    fn memory_safety_map_growth_nested_replacement_and_read_root() {
        let mut zipper = ValueZipper::new();
        let mut expected = BTreeMap::new();
        for index in 0..64 {
            let key: Arc<str> = format!("key{index:03}").into();
            let parent = vec![PathItem::Key(key.clone())];
            zipper.insert_value(&parent, Value::Array(Vec::new()));
            for child in 0..8 {
                let path = vec![parent[0].clone(), PathItem::Index(child)];
                zipper.insert_value(&path, Value::Boolean(child % 2 == 0));
                assert!(matches!(zipper.read_root(), Value::Object(_)));
                assert_eq!(zipper.with_leaf(&path).1, &Value::Boolean(child % 2 == 0));
            }
            zipper.with_leaf(&parent);
            zipper.insert_value(&parent, Value::String(format!("replaced{index}")));
            expected.insert(key, Value::String(format!("replaced{index}")));
        }
        zipper.with_leaf(&vec![]);
        assert_eq!(zipper.take_root(), Value::Object(expected));
    }

    #[test]
    fn memory_safety_repeated_key_sparse_index_and_ancestor_replacement() {
        let mut zipper = ValueZipper::new();
        let parent = vec![PathItem::Key("key".into())];
        zipper.insert_value(&parent, Value::Null);
        let child = vec![parent[0].clone(), PathItem::Index(32)];
        zipper.insert_value(&child, Value::Boolean(true));
        zipper.with_leaf(&parent);
        let mut expected = vec![Value::Null; 33];
        expected[32] = Value::Boolean(true);
        assert_eq!(zipper.with_leaf(&parent).1, &Value::Array(expected));
        zipper.insert_value(&parent, Value::Null);
        zipper.insert_value(&child, Value::Boolean(false));
        zipper.with_leaf(&parent);
        zipper.with_leaf(&vec![]);
        zipper.insert_value(&vec![], Value::Null);
        assert_eq!(zipper.take_root(), Value::Null);
    }
}
