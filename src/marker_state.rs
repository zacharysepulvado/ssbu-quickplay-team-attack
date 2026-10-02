//! Local, process-only status for a future versus-screen indicator.
//!
//! A submitted proposal is not the selected rule. Publish only after the
//! selected record has been copied, and clear the prior result at the next
//! selection. No network message or game rule is changed here.

use core::sync::atomic::{AtomicU8, Ordering};

#[repr(u8)]
#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Status {
    Unknown = 0,
    Off = 1,
    On = 2,
}

static SELECTED: AtomicU8 = AtomicU8::new(Status::Unknown as u8);

pub fn reset() {
    SELECTED.store(Status::Unknown as u8, Ordering::Release);
}

pub fn publish(mode: u32, request: u32, selected_team: u8) {
    let status = if mode == crate::application::COOP_MODE && request == 2 {
        match selected_team {
            0 => Status::Off,
            1 => Status::On,
            _ => Status::Unknown,
        }
    } else {
        Status::Unknown
    };
    SELECTED.store(status as u8, Ordering::Release);
}

pub fn current() -> Status {
    match SELECTED.load(Ordering::Acquire) {
        1 => Status::Off,
        2 => Status::On,
        _ => Status::Unknown,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn only_selected_coop_rules_have_a_known_status() {
        reset();
        assert_eq!(current(), Status::Unknown);
        publish(crate::application::COOP_MODE, 2, 1);
        assert_eq!(current(), Status::On);
        reset();
        assert_eq!(current(), Status::Unknown);
        publish(crate::application::COOP_MODE, 2, 0);
        assert_eq!(current(), Status::Off);
        publish(crate::application::COOP_MODE, 2, 0xff);
        assert_eq!(current(), Status::Unknown);
        publish(crate::application::COOP_MODE, 0, 1);
        assert_eq!(current(), Status::Unknown);
        publish(0, 2, 1);
        assert_eq!(current(), Status::Unknown);
    }
}
