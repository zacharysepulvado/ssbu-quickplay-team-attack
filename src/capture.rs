//! Fixed, single-use slots: no lazy initialization, lock, heap, or reuse.
use std::{
    cell::UnsafeCell,
    mem::MaybeUninit,
    sync::atomic::{AtomicU8, AtomicUsize, Ordering},
};

pub const COMPACT_BUFFER_LEN: usize = 0x69;
pub const CAPTURE_CAPACITY: usize = 256;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Capture {
    pub sequence: usize,
    pub bytes: [u8; COMPACT_BUFFER_LEN],
}

struct Slot {
    // 0: unpublished, 1: ready, 2: consumed.
    state: AtomicU8,
    value: UnsafeCell<MaybeUninit<Capture>>,
}

impl Slot {
    const fn new() -> Self {
        Self {
            state: AtomicU8::new(0),
            value: UnsafeCell::new(MaybeUninit::uninit()),
        }
    }
}

// Each slot has one producer, one successful consumer, and no reuse.
// Release/acquire publication orders all payload accesses.
unsafe impl Sync for Slot {}

pub struct CaptureStore {
    next: AtomicUsize,
    slots: [Slot; CAPTURE_CAPACITY],
}

impl Default for CaptureStore {
    fn default() -> Self {
        Self::new()
    }
}

impl CaptureStore {
    pub const fn new() -> Self {
        Self {
            next: AtomicUsize::new(0),
            slots: [const { Slot::new() }; CAPTURE_CAPACITY],
        }
    }

    /// One weak CAS attempt; contention or a spurious failure drops the sample.
    pub fn try_capture(
        &self,
        limit: usize,
        sample: impl FnOnce() -> [u8; COMPACT_BUFFER_LEN],
    ) -> bool {
        let index = self.next.load(Ordering::Relaxed);
        if index >= limit.min(CAPTURE_CAPACITY) {
            return false;
        }
        if self
            .next
            .compare_exchange_weak(index, index + 1, Ordering::Relaxed, Ordering::Relaxed)
            .is_err()
        {
            return false;
        }
        let capture = Capture {
            sequence: index,
            bytes: sample(),
        };
        // SAFETY: index was bounded; only this producer owns this slot.
        let slot = unsafe { self.slots.get_unchecked(index) };
        unsafe {
            (*slot.value.get()).write(capture);
        }
        slot.state.store(1, Ordering::Release);
        true
    }

    pub fn take(&self, index: usize) -> Option<Capture> {
        let slot = self.slots.get(index)?;
        slot.state
            .compare_exchange(1, 2, Ordering::Acquire, Ordering::Relaxed)
            .ok()?;
        // SAFETY: publication initialized the slot; only this consumer won.
        Some(unsafe { (*slot.value.get()).assume_init_read() })
    }

    pub fn reserved(&self) -> usize {
        self.next.load(Ordering::Relaxed)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn bounded_and_never_reused() {
        let store = CaptureStore::new();
        for index in 0..CAPTURE_CAPACITY {
            // The production path never retries. The test may retry a spurious
            // weak-CAS failure while filling the store to exercise its bound.
            while !store.try_capture(usize::MAX, || [index as u8; COMPACT_BUFFER_LEN]) {}
        }
        assert!(!store.try_capture(usize::MAX, || panic!("full store sampled")));
        for index in 0..CAPTURE_CAPACITY {
            assert_eq!(
                store.take(index).unwrap().bytes,
                [index as u8; COMPACT_BUFFER_LEN]
            );
            assert!(store.take(index).is_none());
        }
        assert!(!store.try_capture(usize::MAX, || panic!("reused a slot")));
        assert!(store.take(CAPTURE_CAPACITY).is_none());
    }

    #[test]
    fn zero_limit_does_not_sample() {
        assert!(!CaptureStore::new().try_capture(0, || panic!("zero limit sampled")));
    }

    #[test]
    fn concurrent_producers_publish_complete_payloads() {
        let store = std::sync::Arc::new(CaptureStore::new());
        let threads: Vec<_> = (1..=8)
            .map(|value| {
                let store = store.clone();
                std::thread::spawn(move || {
                    for _ in 0..128 {
                        store.try_capture(256, || [value; COMPACT_BUFFER_LEN]);
                    }
                })
            })
            .collect();
        for thread in threads {
            thread.join().unwrap();
        }
        for index in 0..store.reserved() {
            let capture = store.take(index).unwrap();
            assert_eq!(capture.sequence, index);
            assert!((1..=8).contains(&capture.bytes[0]));
            assert!(capture.bytes.iter().all(|byte| *byte == capture.bytes[0]));
        }
    }
}
