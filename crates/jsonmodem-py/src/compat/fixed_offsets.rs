//! Call-local fixed-timezone offsets retain the owner used for identity checks.

#![forbid(unsafe_code)]

const CAPACITY: usize = 8;
const MAX_MISSES: usize = CAPACITY * 2;

/// Bounds retained owners independently of the number of serialized datetimes.
pub(super) struct FixedOffsets<Owner> {
    entries: [Option<(Owner, i64)>; CAPACITY],
    // None disables the cache, either by caller choice or after repeated misses.
    next: Option<usize>,
    // Stops at MAX_MISSES; a successful lookup resets this to zero.
    consecutive_misses: usize,
}

impl<Owner> FixedOffsets<Owner> {
    pub(super) fn new(enabled: bool) -> Self {
        Self {
            entries: std::array::from_fn(|_| None),
            next: enabled.then_some(0),
            consecutive_misses: 0,
        }
    }

    pub(super) fn get(&mut self, mut same_owner: impl FnMut(&Owner) -> bool) -> Option<i64> {
        self.next?;
        let found = self
            .entries
            .iter()
            .flatten()
            .find_map(|(owner, seconds)| same_owner(owner).then_some(*seconds));
        if found.is_some() {
            self.consecutive_misses = 0;
        } else {
            self.consecutive_misses += 1;
            if self.consecutive_misses == MAX_MISSES {
                // Keep owners until the call ends, rather than changing release order here.
                self.next = None;
            }
        }
        found
    }

    pub(super) fn enabled(&self) -> bool {
        self.next.is_some()
    }

    pub(super) fn insert(&mut self, make_entry: impl FnOnce() -> (Owner, i64)) {
        let Some(index) = self.next else {
            return;
        };
        let entry = make_entry();
        self.next = Some((index + 1) % CAPACITY);
        self.entries[index] = Some(entry);
    }
}

#[cfg(test)]
mod tests {
    use std::{cell::RefCell, rc::Rc};

    use super::{CAPACITY, FixedOffsets, MAX_MISSES};

    #[test]
    fn empty_cache_does_not_inspect_an_owner() {
        let mut cache = FixedOffsets::<usize>::new(true);
        assert!(cache.enabled());
        assert_eq!(cache.get(|_| panic!("no owner exists")), None);
    }

    #[test]
    fn portable_cache_does_not_create_or_inspect_entries() {
        let mut cache = FixedOffsets::<usize>::new(false);
        assert!(!cache.enabled());
        cache.insert(|| panic!("portable mode must not retain an owner"));
        assert_eq!(cache.get(|_| panic!("portable lookup")), None);
        assert!(cache.entries.iter().all(Option::is_none));
    }

    #[test]
    fn lookup_distinguishes_owners_with_equal_values() {
        let first = Rc::new(1);
        let second = Rc::new(1);
        let mut cache = FixedOffsets::new(true);
        cache.insert(|| (first.clone(), -3600));
        cache.insert(|| (second.clone(), 7200));
        assert_eq!(cache.get(|owner| Rc::ptr_eq(owner, &first)), Some(-3600));
        assert_eq!(cache.get(|owner| Rc::ptr_eq(owner, &second)), Some(7200));
        assert_eq!(Rc::strong_count(&first), 2);
        assert_eq!(Rc::strong_count(&second), 2);
    }

    #[test]
    fn eviction_releases_only_the_replaced_owner() {
        let owners: Vec<_> = (0..=CAPACITY).map(Rc::new).collect();
        let mut cache = FixedOffsets::new(true);
        for (index, owner) in owners.iter().take(CAPACITY).enumerate() {
            cache.insert(|| (owner.clone(), index as i64));
        }
        cache.insert(|| (owners[CAPACITY].clone(), i64::MAX));
        assert_eq!(Rc::strong_count(&owners[0]), 1);
        assert_eq!(cache.get(|owner| Rc::ptr_eq(owner, &owners[0])), None);
        assert!(owners[1..].iter().all(|owner| Rc::strong_count(owner) == 2));
        assert_eq!(
            cache.get(|owner| Rc::ptr_eq(owner, &owners[CAPACITY])),
            Some(i64::MAX)
        );
        drop(cache);
        assert!(owners.iter().all(|owner| Rc::strong_count(owner) == 1));
    }

    #[test]
    fn moving_cache_preserves_its_owners_and_offsets() {
        let owner = Rc::new(9);
        let mut cache = {
            let mut original = FixedOffsets::new(true);
            original.insert(|| (owner.clone(), i64::MIN));
            original
        };
        assert_eq!(cache.get(|entry| Rc::ptr_eq(entry, &owner)), Some(i64::MIN));
        drop(cache);
        assert_eq!(Rc::strong_count(&owner), 1);
    }

    #[test]
    fn separate_calls_have_separate_caches() {
        let mut first = FixedOffsets::new(true);
        let mut second = FixedOffsets::<usize>::new(true);
        first.insert(|| (1, 3600));
        assert_eq!(first.get(|owner| *owner == 1), Some(3600));
        assert_eq!(second.get(|_| true), None);
    }

    #[test]
    fn failed_entry_construction_keeps_the_previous_cache() {
        let mut cache = FixedOffsets::new(true);
        cache.insert(|| (1, 3600));
        let next = cache.next;
        let result = std::panic::catch_unwind(std::panic::AssertUnwindSafe(|| {
            cache.insert(|| panic!("entry construction failed"));
        }));
        assert!(result.is_err());
        assert_eq!(cache.next, next);
        assert_eq!(cache.get(|owner| *owner == 1), Some(3600));
    }

    #[test]
    fn repeated_misses_stop_lookup_and_entry_construction() {
        let mut cache = FixedOffsets::new(true);
        cache.insert(|| (1, 3600));
        for _ in 0..MAX_MISSES {
            assert_eq!(cache.get(|_| false), None);
        }
        assert!(!cache.enabled());
        assert_eq!(cache.get(|_| panic!("disabled lookup")), None);
        cache.insert(|| panic!("disabled insertion"));
    }

    #[test]
    fn hits_reset_the_consecutive_miss_count() {
        let mut cache = FixedOffsets::new(true);
        cache.insert(|| (1, 3600));
        for _ in 0..4 {
            for _ in 1..MAX_MISSES {
                assert_eq!(cache.get(|_| false), None);
            }
            assert_eq!(cache.get(|owner| *owner == 1), Some(3600));
        }
        assert!(cache.enabled());
    }

    #[test]
    fn disabling_after_misses_does_not_release_owners_early() {
        let owner = Rc::new(1);
        let mut cache = FixedOffsets::new(true);
        cache.insert(|| (owner.clone(), 3600));
        for _ in 0..MAX_MISSES {
            assert_eq!(cache.get(|_| false), None);
        }
        assert_eq!(Rc::strong_count(&owner), 2);
        drop(cache);
        assert_eq!(Rc::strong_count(&owner), 1);
    }

    /// Records release so wraparound and final drop can be checked together.
    struct Owner {
        id: usize,
        released: Rc<RefCell<Vec<usize>>>,
    }

    impl Drop for Owner {
        fn drop(&mut self) {
            self.released.borrow_mut().push(self.id);
        }
    }

    #[test]
    fn repeated_eviction_and_drop_release_each_owner_once() {
        const COUNT: usize = CAPACITY * 5 + 3;
        let released = Rc::new(RefCell::new(Vec::new()));
        let mut cache = FixedOffsets::new(true);
        for id in 0..COUNT {
            cache.insert(|| {
                (
                    Owner {
                        id,
                        released: released.clone(),
                    },
                    id as i64,
                )
            });
        }
        assert_eq!(
            *released.borrow(),
            (0..COUNT - CAPACITY).collect::<Vec<_>>()
        );
        let retained: Vec<_> = (COUNT - CAPACITY..COUNT)
            .map(|id| cache.get(|owner| owner.id == id))
            .collect();
        assert_eq!(
            retained,
            (COUNT - CAPACITY..COUNT)
                .map(|id| Some(id as i64))
                .collect::<Vec<_>>()
        );
        drop(cache);
        released.borrow_mut().sort_unstable();
        assert_eq!(*released.borrow(), (0..COUNT).collect::<Vec<_>>());
    }
}
