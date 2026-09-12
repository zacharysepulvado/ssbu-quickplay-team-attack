//! Pure validation shared by host tests and the Switch entry point.
use crate::{
    capture::{CAPTURE_CAPACITY, COMPACT_BUFFER_LEN},
    config::{Config, Mode, SUPPORTED_GAME_VERSION},
};

pub type ValidationResult<T> = Result<T, &'static str>;

pub fn validate_config(config: &Config, live_version: &str) -> ValidationResult<()> {
    if !config.enabled || config.mode == Mode::Disabled {
        return Err("plugin is disabled");
    }
    if live_version != SUPPORTED_GAME_VERSION || config.expected_game_version != live_version {
        return Err("runtime game version is not the reviewed 13.0.5 version");
    }
    // These are research attestations, not a runtime proof of an ABI or allocation.
    if !config.evidence_reviewed || !config.offline_test_acknowledged {
        return Err("offline ABI/layout/caller evidence has not been acknowledged");
    }
    if config.reviewed_abi != "void_u8_ptr_v1" || config.reviewed_buffer_len != COMPACT_BUFFER_LEN {
        return Err("unsupported or unreviewed serializer ABI/buffer length");
    }
    if !(1..=CAPTURE_CAPACITY).contains(&config.max_dumps) {
        return Err("capture limit out of bounds");
    }
    if config.observe_rule_application
        && (!config.observe_rule_codec || !config.poll_global_team_attack)
    {
        return Err("application observer requires the codec and bounded global watcher");
    }
    if config.mode == Mode::ProposalExperiment && !config.observe_rule_application {
        return Err("proposal experiment requires the guarded application hooks");
    }
    if config.observe_rule_codec && !config.poll_global_team_attack {
        return Err("codec batch requires the global watcher and its 20-minute limit");
    }
    if config.capture_offsets.is_empty() || config.capture_offsets.len() > 46 {
        return Err("explicit reviewed rule-byte allowlist is required");
    }
    let mut seen = [false; COMPACT_BUFFER_LEN];
    for &offset in &config.capture_offsets {
        if !matches!(offset, 0x04..=0x2c | 0x58..=0x5c) {
            return Err("non-rule/padding/profile byte refused");
        }
        if seen[offset as usize] {
            return Err("duplicate capture offset");
        }
        seen[offset as usize] = true;
    }
    for (offset, signature) in [
        (config.serializer_text_offset, &config.expected_prologue),
        (config.caller_text_offset, &config.expected_callsite),
    ] {
        if offset == 0 || offset % 4 != 0 {
            return Err("offset must be nonzero and 4-byte aligned");
        }
        if !(16..=64).contains(&signature.len()) || signature.len() % 4 != 0 {
            return Err("exact signatures must be 16..64 bytes in 4-byte units");
        }
    }
    let target_end = config
        .serializer_text_offset
        .checked_add(config.expected_prologue.len())
        .ok_or("offset overflow")?;
    let caller_end = config
        .caller_text_offset
        .checked_add(config.expected_callsite.len())
        .ok_or("offset overflow")?;
    if config.serializer_text_offset < caller_end && config.caller_text_offset < target_end {
        return Err("entry and caller signatures overlap");
    }
    Ok(())
}

pub fn validate_region(text: usize, rodata: usize) -> ValidationResult<usize> {
    let size = rodata
        .checked_sub(text)
        .ok_or("invalid executable region")?;
    if text == 0 || !text.is_multiple_of(4) || !(64..=128 * 1024 * 1024).contains(&size) {
        return Err("invalid executable region");
    }
    Ok(size)
}

pub fn validate_signatures(config: &Config, text: &[u8]) -> ValidationResult<()> {
    for (offset, signature) in [
        (config.serializer_text_offset, &config.expected_prologue),
        (config.caller_text_offset, &config.expected_callsite),
    ] {
        if signature.len() < 16 {
            return Err("signature too short");
        }
        let end = offset
            .checked_add(signature.len())
            .ok_or("offset overflow")?;
        if text.get(offset..end) != Some(signature.as_slice()) {
            return Err("live code signature mismatch or outside text");
        }
        if text
            .windows(signature.len())
            .step_by(4)
            .filter(|window| *window == signature.as_slice())
            .take(2)
            .count()
            != 1
        {
            return Err("signature is not unique at aligned addresses");
        }
    }
    let bytes: [u8; 4] = config
        .expected_callsite
        .get(..4)
        .ok_or("call signature missing")?
        .try_into()
        .map_err(|_| "call signature missing")?;
    if bl_target(config.caller_text_offset, u32::from_le_bytes(bytes))
        != Some(config.serializer_text_offset)
    {
        return Err("callsite does not begin with a direct BL to this serializer");
    }
    Ok(())
}

pub fn bl_target(instruction_offset: usize, instruction: u32) -> Option<usize> {
    if instruction & 0xfc00_0000 != 0x9400_0000 {
        return None;
    }
    let displacement = (((instruction & 0x03ff_ffff) << 6) as i32 >> 4) as i64;
    let base = i64::try_from(instruction_offset).ok()?;
    usize::try_from(base.checked_add(displacement)?).ok()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn fixture() -> (Config, Vec<u8>) {
        let mut config = Config {
            enabled: true,
            mode: Mode::Observe,
            evidence_reviewed: true,
            offline_test_acknowledged: true,
            reviewed_abi: "void_u8_ptr_v1".into(),
            reviewed_buffer_len: COMPACT_BUFFER_LEN,
            capture_offsets: vec![4, 0x58],
            serializer_text_offset: 32,
            caller_text_offset: 96,
            expected_prologue: (1..=16).collect(),
            expected_callsite: (20..36).collect(),
            ..Config::default()
        };
        config.expected_callsite[..4].copy_from_slice(&0x97ff_fff0_u32.to_le_bytes());
        let mut text = vec![0; 256];
        text[32..48].copy_from_slice(&config.expected_prologue);
        text[96..112].copy_from_slice(&config.expected_callsite);
        (config, text)
    }

    #[test]
    fn valid_fixture_and_runtime_version_gate() {
        let (config, text) = fixture();
        assert!(validate_config(&config, "13.0.5").is_ok());
        assert!(validate_signatures(&config, &text).is_ok());
        assert!(validate_config(&config, "13.0.4").is_err());
        assert!(validate_config(&Config::default(), "13.0.5").is_err());
    }

    #[test]
    fn rejects_bad_evidence_bounds_and_privacy() {
        let (mut config, _) = fixture();
        config.evidence_reviewed = false;
        assert!(validate_config(&config, "13.0.5").is_err());
        config.evidence_reviewed = true;
        config.reviewed_buffer_len = 104;
        assert!(validate_config(&config, "13.0.5").is_err());
        config.reviewed_buffer_len = 105;
        config.capture_offsets = vec![0x60];
        assert!(validate_config(&config, "13.0.5").is_err());
        assert!(validate_region(0, 4096).is_err());
        assert!(validate_region(8192, 4096).is_err());
        assert_eq!(validate_region(4096, 8192).unwrap(), 4096);
    }

    #[test]
    fn rejects_mismatch_duplicates_and_overflow() {
        let (mut config, mut text) = fixture();
        text[32] ^= 1;
        assert!(validate_signatures(&config, &text).is_err());
        text[32] ^= 1;
        text[160..176].copy_from_slice(&config.expected_prologue);
        assert!(validate_signatures(&config, &text).is_err());
        config.serializer_text_offset = usize::MAX - 3;
        assert!(validate_signatures(&config, &text).is_err());
    }

    #[test]
    fn direct_bl_decoding_is_signed() {
        assert_eq!(bl_target(96, 0x97ff_fff0), Some(32));
        assert_eq!(bl_target(32, 0x9400_0010), Some(96));
        assert_eq!(bl_target(0, 0x97ff_fff0), None);
        assert_eq!(bl_target(32, 0xd503_201f), None);
    }
}
