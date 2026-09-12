//! Reviewed 13.0.5 global-field observation, independent of serializer calls.
//! No global is written. A global value is not an effective match-rule value.
use crate::{config::Config, validation::ValidationResult};

pub const GLOBAL_OFFSET: usize = 0x530_a981;
pub const GUARD_OFFSET: usize = 0x531_44d8;
pub const HEARTBEAT_MS: u64 = 5_000;
pub const WATCH_LIMIT_MS: u64 = 20 * 60 * 1_000;

/// Decode ADRP to a module-relative page. Text must be page aligned at runtime.
fn adrp_page(pc: usize, instruction: u32, register: u32) -> Option<usize> {
    if instruction & 0x9f00_001f != 0x9000_0000 | register {
        return None;
    }
    let immediate = (((instruction >> 5) & 0x7ffff) << 2) | ((instruction >> 29) & 3);
    let displacement = (((immediate << 11) as i32) >> 11) as i64 * 4096;
    usize::try_from((pc & !0xfff) as i64 + displacement).ok()
}

pub fn validate_source(config: &Config, text: &[u8]) -> ValidationResult<()> {
    if config.serializer_text_offset != 0x16e_2c50 || config.capture_offsets != [0x11] {
        return Err("global watcher requires the reviewed 13.0.5 serializer and byte 11");
    }
    let base = config.serializer_text_offset;
    let word = |relative: usize| -> ValidationResult<u32> {
        let bytes = text
            .get(base + relative..base + relative + 4)
            .ok_or("global source instruction outside text")?;
        Ok(u32::from_le_bytes(bytes.try_into().unwrap()))
    };
    // User-exported disassembly: x8 = main+0x5308000+0x768;
    // x10 = *(u64 *)(x8+0x2214), stored at output+0x0c.
    // Byte output+0x11 is therefore source+5 = main+0x530a981.
    if adrp_page(base + 0x30, word(0x30)?, 8) != Some(0x530_8000)
        || word(0x34)? != 0x911d_a108 // add x8,x8,#0x768
        || word(0x5c)? != 0x5284_428a // mov w10,#0x2214
        || word(0x68)? != 0xf86a_690a // ldr x10,[x8,x10]
        || word(0x74)? != 0xf800_c26a // stur x10,[x19,#0xc]
        || adrp_page(base + 0x1c, word(0x1c)?, 20) != Some(0x531_4000)
        || word(0x20)? != 0x9113_6294
    // add x20,x20,#0x4d8
    {
        return Err("reviewed global/guard source instruction mismatch");
    }
    Ok(())
}

/// Validate the kernel's mapping result before reading a byte of game memory.
pub fn validate_mapping(
    address: usize,
    data_start: usize,
    start: u64,
    size: u64,
    memory_type: u32,
    permission: u32,
) -> ValidationResult<()> {
    let end = start.checked_add(size).ok_or("memory mapping overflow")?;
    if data_start == 0
        || address < data_start
        || (address as u64) < start
        || (address as u64) >= end
        || permission & 7 != 3
        || !matches!(memory_type & 0xff, 4 | 9)
    {
        return Err("global byte is outside readable module data");
    }
    Ok(())
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Observation {
    pub initialized: bool,
    pub value: Option<u8>,
    pub serializer_calls: usize,
    pub stored_dumps: usize,
}

#[derive(Default)]
pub struct WatchSchedule {
    last: Option<Observation>,
    last_ms: u64,
}

impl WatchSchedule {
    pub fn should_log(&mut self, elapsed_ms: u64, observation: Observation) -> bool {
        if self.last != Some(observation) || elapsed_ms.saturating_sub(self.last_ms) >= HEARTBEAT_MS
        {
            self.last = Some(observation);
            self.last_ms = elapsed_ms;
            true
        } else {
            false
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn adrp(pc: usize, target: usize, rd: u32) -> u32 {
        let pages = ((target as i64 - (pc & !0xfff) as i64) / 4096) as u32 & 0x1fffff;
        0x90000000 | (pages & 3) << 29 | (pages >> 2) << 5 | rd
    }

    #[test]
    fn source_validation_rejects_changed_load_and_wrong_profile() {
        let base = 0x16e2c50;
        let config = Config {
            serializer_text_offset: base,
            capture_offsets: vec![0x11],
            ..Config::default()
        };
        let mut code = vec![0; base + 0x78];
        for (offset, instruction) in [
            (0x30, adrp(base + 0x30, 0x5308000, 8)),
            (0x34, 0x911da108),
            (0x5c, 0x5284428a),
            (0x68, 0xf86a690a),
            (0x74, 0xf800c26a),
            (0x1c, adrp(base + 0x1c, 0x5314000, 20)),
            (0x20, 0x91136294),
        ] {
            code[base + offset..base + offset + 4].copy_from_slice(&instruction.to_le_bytes());
        }
        assert!(validate_source(&config, &code).is_ok());
        code[base + 0x68] ^= 1;
        assert!(validate_source(&config, &code).is_err());
        assert!(validate_source(&Config::default(), &code).is_err());
        assert!(validate_source(&config, &[]).is_err());
        assert_eq!(adrp_page(0x5000, adrp(0x5000, 0x1000, 8), 8), Some(0x1000));
    }

    #[test]
    fn rejects_unmapped_executable_heap_and_wrapped_regions() {
        assert!(validate_mapping(0x1081, 0x1000, 0x1000, 0x1000, 4, 3).is_ok());
        for (address, start, size, kind, permission) in [
            (0x3000, 0x1000, 0x1000, 4, 3),
            (0x1081, 0x1000, 0x1000, 4, 5),
            (0x1081, 0x1000, 0x1000, 5, 3),
            (0x1081, 0x1000, 0x1000, 0, 0),
            (0x1081, u64::MAX, 1, 4, 3),
        ] {
            assert!(validate_mapping(address, 0x1000, start, size, kind, permission).is_err());
        }
    }

    #[test]
    fn startup_changes_and_heartbeat_record_without_any_serializer_calls() {
        let mut schedule = WatchSchedule::default();
        let mut state = Observation {
            initialized: false,
            value: None,
            serializer_calls: 0,
            stored_dumps: 0,
        };
        assert!(schedule.should_log(0, state));
        assert!(!schedule.should_log(250, state));
        assert!(schedule.should_log(5000, state));
        state.initialized = true;
        state.value = Some(0);
        assert!(schedule.should_log(5250, state));
        state.value = Some(1);
        assert!(schedule.should_log(5500, state));
        state.value = Some(0);
        assert!(schedule.should_log(5750, state));
        assert!(!schedule.should_log(6000, state));
        assert!(schedule.should_log(10750, state));
    }
}
