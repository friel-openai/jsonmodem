//! Cached branch access for value building. Pointer dereferences are confined
//! here; returned references borrow the owning zipper.

use core::{cmp::Ordering, ptr::NonNull};

use super::{Path, StdPath, Value, ValueZipper, descend_one};

impl ValueZipper {
    #[inline]
    pub(super) fn align_path(&mut self, path: &Path) -> (&StdPath, &mut Value) {
        let current_depth = self.path_components.len();
        let target_depth = path.len();

        match target_depth.cmp(&current_depth) {
            Ordering::Greater => {
                #[cfg(any(fuzzing, debug_assertions))]
                assert_eq!(
                    target_depth,
                    current_depth + 1,
                    "parser path depth increased by more than one"
                );
                let mut parent_ptr = self.current_ptr();
                let component = path
                    .last()
                    .expect("path depth greater than current depth implies non-empty path");
                // SAFETY: the current node is live and exclusively borrowed.
                // No descendant pointers exist while its container may grow.
                let child = descend_one(unsafe { parent_ptr.as_mut() }, component);
                let child_ptr = NonNull::from(child);
                self.path_nodes.push(child_ptr);
                self.path_components.push(component.clone());
            }
            Ordering::Less => {
                #[cfg(any(fuzzing, debug_assertions))]
                assert_eq!(
                    current_depth,
                    target_depth + 1,
                    "parser path depth decreased by more than one"
                );
                self.path_nodes.truncate(target_depth);
                self.path_components.truncate(target_depth);
            }
            Ordering::Equal => {
                if let Some(last) = path.last() {
                    let matches_existing = self.path_components.last() == Some(last);
                    if !matches_existing {
                        self.path_nodes.pop();
                        self.path_components.pop();
                        let mut parent_ptr = self.current_ptr();
                        // SAFETY: the old child pointer was removed before
                        // descend_one can grow the parent's container.
                        let child = descend_one(unsafe { parent_ptr.as_mut() }, last);
                        let child_ptr = NonNull::from(child);
                        self.path_nodes.push(child_ptr);
                        self.path_components.push(last.clone());
                    }
                }
            }
        }

        // SAFETY: the branches above retain only pointers to live ancestors
        // and the current leaf. The leaf belongs to the boxed tree, disjoint
        // from path_components. Both references remain tied to this zipper.
        let leaf = unsafe { self.current_ptr().as_mut() };
        (&self.path_components, leaf)
    }

    #[inline]
    fn current_ptr(&mut self) -> NonNull<Value> {
        match self.path_nodes.last().copied() {
            Some(ptr) => ptr,
            None => NonNull::from(self.root.as_mut()),
        }
    }
}
