//! Reviewed, bounded rule-application events. No player identifiers or payloads.
use crate::capture::COMPACT_BUFFER_LEN;

pub const BANK_LIMIT: usize = 64;
pub const COOP_MODE: u32 = 0x07010102;
pub const MODE_OFFSET: usize = 0x53050f0;
pub const SESSION_REQUEST: usize = 0x269c0;
pub const SESSION_PREPARED: usize = 0x26a62;
pub const LOCAL_TEAM: usize = 0x21fa9;
pub const SELECTED_TEAM: usize = 0x24649;
pub const SITE_COUNT: usize = 8;
pub const SITES: [usize; SITE_COUNT] = [
    0x169bf4c, 0x169ec00, 0x169c3a8, 0x169c92c, 0x169c93c, 0x1685ccc, 0x16f056c, 0x16f0598,
];
pub const NAMES: [&str; SITE_COUNT] = [
    "local_copy",
    "participant_copy",
    "selection_ready",
    "apply_before",
    "apply_after",
    "rule_submit",
    "rule_receive_before",
    "rule_receive_team_stored",
];

pub const SUBMIT_ORIGINS: [&str; 4] = ["state_update", "local_record", "per_slot", "initial_local"];
pub const MUTATION_ACTIONS: [&str; 2] = ["proposal_00_to_01", "local_mirror_00_to_01"];

/// At the generic B4 submission hook x30 still contains the direct caller's
/// return address. Keep only a reviewed four-value classification; never log
/// a code address.
pub fn submit_origin(return_offset: usize) -> u8 {
    match return_offset {
        0x1687fec => 0,
        0x1690884 => 1,
        0x16f52d8 => 2,
        0x16fa0e8 => 3,
        _ => 0xff,
    }
}

/// Mirror the reviewed 0x16F6340 identity-to-slot comparison over sixteen
/// entries spaced 0x78 bytes apart. Inputs are pointers, but only the bounded
/// result is retained or logged.
pub fn identity_slot(identity: usize, entries: &[usize; 16]) -> Option<u8> {
    if identity == 0 {
        return None;
    }
    entries
        .iter()
        .position(|entry| *entry == identity)
        .map(|slot| slot as u8)
}

#[allow(clippy::too_many_arguments)]
pub fn proposal_guard(
    mode: u32,
    request: u32,
    prepared: u8,
    initialized: bool,
    global_team: u8,
    local_slot: u8,
    proposal_slot: u8,
    proposal_team: u8,
    submit_origin: u8,
) -> bool {
    mode == COOP_MODE
        && request == 2
        && prepared == 0
        && initialized
        && global_team == 0
        && local_slot < 16
        && proposal_slot == local_slot
        && proposal_team == 0
        && submit_origin < SUBMIT_ORIGINS.len() as u8
}

/// Return only a bounded slot number; never put a participant pointer in a log.
pub fn participant_slot(session: usize, source: usize) -> Option<u8> {
    let delta = source.checked_sub(session.checked_add(0xa798)?)?;
    if !delta.is_multiple_of(0x1350) || delta / 0x1350 >= 16 {
        return None;
    }
    Some((delta / 0x1350) as u8)
}

pub const BODIES: &[(usize, &[u8])] = &[
    (0x169bef0, include_bytes!("reviewed/application.bin")),
    (0x16eb720, include_bytes!("reviewed/restore.bin")),
    (0x16e3ec0, include_bytes!("reviewed/participant_copy.bin")),
    (0x16ea390, include_bytes!("reviewed/chooser.bin")),
    (0x1685cb0, include_bytes!("reviewed/submit_entry.bin")),
    (0x16f03b0, include_bytes!("reviewed/receive_entry.bin")),
    (0x16f0550, include_bytes!("reviewed/receive_b4.bin")),
];
pub const SUBMIT_CALL_SITES: &[(usize, [u8; 4])] = &[
    (0x1687fe8, [0x32, 0xf7, 0xff, 0x97]),
    (0x1690880, [0x0c, 0xd5, 0xff, 0x97]),
    (0x16f52d4, [0x77, 0x42, 0xfe, 0x97]),
    (0x16fa0e4, [0xf3, 0x2e, 0xfe, 0x97]),
];

/// B4 must dispatch to the independently reviewed copy branch. The caller
/// supplies mapped rodata only, checked against Skyline module boundaries.
pub fn validate_receive_table(rodata: &[u8], rodata_offset: usize) -> Result<(), String> {
    let a = 0x44f3b48usize
        .checked_sub(rodata_offset)
        .ok_or("receive table precedes rodata")?;
    let expected = (0x16f0550i32 - 0x44f3b44i32).to_le_bytes();
    if rodata.get(a..a + 4) != Some(expected.as_slice()) {
        return Err("B4 receive dispatch table mismatch".into());
    }
    Ok(())
}
pub fn received_slot(manager: usize, record: usize) -> Option<u8> {
    let delta = record.checked_sub(manager)?;
    if !delta.is_multiple_of(0x1350) || delta / 0x1350 >= 16 {
        return None;
    }
    Some((delta / 0x1350) as u8)
}

pub fn validate(text: &[u8]) -> Result<(), String> {
    for &(offset, expected) in BODIES {
        if text.get(offset..offset + expected.len()) != Some(expected) {
            return Err(format!(
                "rule application body mismatch at main+{offset:#x}"
            ));
        }
    }
    for &(offset, expected) in SUBMIT_CALL_SITES {
        if text.get(offset..offset + expected.len()) != Some(expected.as_slice()) {
            return Err(format!("B4 submit caller mismatch at main+{offset:#x}"));
        }
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Event {
    pub kind: u8,
    pub prepared: u8,
    pub team: u8,
    pub global: u8,
    pub initialized: bool,
    pub participant: u8, // FF means not applicable/invalid, never an account ID.
    pub local_slot: u8,
    pub selected_owner: u8,
    pub submit_origin: u8,
    pub mutation_action: u8,
    pub mode: u32,
    pub request: u32,
    pub elapsed_ticks: u64,
}

impl Event {
    pub fn encode(self) -> [u8; COMPACT_BUFFER_LEN] {
        let mut b = [0; COMPACT_BUFFER_LEN];
        b[..6].copy_from_slice(&[
            self.kind,
            self.prepared,
            self.team,
            self.global,
            self.initialized as u8,
            self.participant,
        ]);
        b[6] = self.local_slot;
        b[7] = self.selected_owner;
        b[8..12].copy_from_slice(&self.mode.to_le_bytes());
        b[12..16].copy_from_slice(&self.request.to_le_bytes());
        b[16..24].copy_from_slice(&self.elapsed_ticks.to_le_bytes());
        b[24] = self.submit_origin;
        b[25] = self.mutation_action;
        b
    }

    pub fn decode(b: &[u8; COMPACT_BUFFER_LEN]) -> Self {
        Self {
            kind: b[0],
            prepared: b[1],
            team: b[2],
            global: b[3],
            initialized: b[4] != 0,
            participant: b[5],
            local_slot: b[6],
            selected_owner: b[7],
            mode: u32::from_le_bytes(b[8..12].try_into().unwrap()),
            request: u32::from_le_bytes(b[12..16].try_into().unwrap()),
            elapsed_ticks: u64::from_le_bytes(b[16..24].try_into().unwrap()),
            submit_origin: b[24],
            mutation_action: b[25],
        }
    }

    pub fn line(self, sequence: usize) -> String {
        format!("application_event: sequence:{sequence} elapsed_ms:{} elapsed_ticks:{} kind:{} mode:{:08X} request:{} prepared:{} rule_team:{:02X} global_team:{:02X} global_initialized:{} participant_slot:{:02X} local_slot:{:02X} selected_owner_slot:{:02X} submit_origin:{} mutation_action:{}",
            self.elapsed_ticks / 19_200, self.elapsed_ticks, NAMES.get(self.kind as usize).unwrap_or(&"invalid"), self.mode, self.request,
            self.prepared, self.team, self.global, u8::from(self.initialized), self.participant,
            self.local_slot, self.selected_owner,
            SUBMIT_ORIGINS.get(self.submit_origin as usize).unwrap_or(&"unknown"),
            MUTATION_ACTIONS.get(self.mutation_action as usize).unwrap_or(&"none"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn receive_index_and_dispatch_fail_closed() {
        for i in 0..16 {
            assert_eq!(received_slot(0x20000, 0x20000 + i * 0x1350), Some(i as u8));
        }
        for p in [0, 0x20001, 0x20000 + 16 * 0x1350, usize::MAX] {
            assert_eq!(received_slot(0x20000, p), None);
        }
        let good = (0x16f0550i32 - 0x44f3b44i32).to_le_bytes();
        validate_receive_table(&good, 0x44f3b48).unwrap();
        assert!(validate_receive_table(&[0; 4], 0x44f3b48).is_err());
        assert!(validate_receive_table(&good[..3], 0x44f3b48).is_err());
        assert!(validate_receive_table(&good, usize::MAX).is_err());
    }
    #[test]
    fn participant_pointer_is_strictly_bounded() {
        for i in 0..16 {
            assert_eq!(
                participant_slot(0x10000, 0x1a798 + i * 0x1350),
                Some(i as u8)
            );
        }
        for p in [0, 0x1a797, 0x1a799, 0x1a798 + 16 * 0x1350, usize::MAX] {
            assert_eq!(participant_slot(0x10000, p), None);
        }
        assert_eq!(participant_slot(usize::MAX, 0), None);
    }
    #[test]
    fn event_retains_full_mode_and_time_and_nonbinary_team_byte() {
        let e = Event {
            kind: 4,
            prepared: 1,
            team: 0xa5,
            global: 0xa5,
            initialized: true,
            participant: 0xff,
            local_slot: 2,
            selected_owner: 3,
            submit_origin: 1,
            mutation_action: 0xff,
            mode: 0x07010102,
            request: 2,
            elapsed_ticks: u32::MAX as u64 + 100,
        };
        assert_eq!(Event::decode(&e.encode()), e);
        assert!(e
            .line(42)
            .contains("local_slot:02 selected_owner_slot:03 submit_origin:local_record"));
    }

    #[test]
    fn submit_callers_and_identity_slots_are_bounded() {
        assert_eq!(submit_origin(0x1687fec), 0);
        assert_eq!(submit_origin(0x1690884), 1);
        assert_eq!(submit_origin(0x16f52d8), 2);
        assert_eq!(submit_origin(0x16fa0e8), 3);
        assert_eq!(submit_origin(0), 0xff);
        let entries = std::array::from_fn(|i| 0x1000 + i * 0x80);
        assert_eq!(identity_slot(entries[11], &entries), Some(11));
        assert_eq!(identity_slot(0, &entries), None);
        assert_eq!(identity_slot(0xdead, &entries), None);
    }
    #[test]
    fn proposal_guard_changes_only_reviewed_local_off_proposals() {
        let good = (COOP_MODE, 2, 0, true, 0, 3, 3, 0, 2);
        assert!(proposal_guard(
            good.0, good.1, good.2, good.3, good.4, good.5, good.6, good.7, good.8
        ));
        let bad = [
            (0, 2, 0, true, 0, 3, 3, 0, 2),
            (COOP_MODE, 1, 0, true, 0, 3, 3, 0, 2),
            (COOP_MODE, 2, 1, true, 0, 3, 3, 0, 2),
            (COOP_MODE, 2, 0, false, 0, 3, 3, 0, 2),
            (COOP_MODE, 2, 0, true, 1, 3, 3, 0, 2),
            (COOP_MODE, 2, 0, true, 0, 0xff, 0xff, 0, 2),
            (COOP_MODE, 2, 0, true, 0, 3, 4, 0, 2),
            (COOP_MODE, 2, 0, true, 0, 3, 3, 1, 2),
            (COOP_MODE, 2, 0, true, 0, 3, 3, 0, 0xff),
        ];
        for args in bad {
            assert!(!proposal_guard(
                args.0, args.1, args.2, args.3, args.4, args.5, args.6, args.7, args.8
            ));
        }
    }
    #[test]
    fn full_body_validation_rejects_interior_changes_and_truncation() {
        let end = BODIES
            .iter()
            .map(|(a, b)| a + b.len())
            .chain(SUBMIT_CALL_SITES.iter().map(|(a, b)| a + b.len()))
            .max()
            .unwrap();
        let mut text = vec![0; end];
        for &(a, b) in BODIES {
            text[a..a + b.len()].copy_from_slice(b);
        }
        for &(a, b) in SUBMIT_CALL_SITES {
            text[a..a + b.len()].copy_from_slice(&b);
        }
        validate(&text).unwrap();
        for &(a, b) in BODIES {
            let i = a + b.len() / 2;
            text[i] ^= 1;
            assert!(validate(&text).is_err());
            text[i] ^= 1;
        }
        for &(a, _) in SUBMIT_CALL_SITES {
            text[a] ^= 1;
            assert!(validate(&text).is_err());
            text[a] ^= 1;
        }
        assert!(validate(&text[..0x169bf00]).is_err());
    }
}
