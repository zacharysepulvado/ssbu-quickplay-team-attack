use std::{
    collections::BTreeSet,
    fmt,
    fs::File,
    io::{self, Read},
};

pub const CONFIG_PATH: &str = "sd:/ultimate/quickplay_team_attack/config.toml";
pub const SUPPORTED_GAME_VERSION: &str = "13.0.5";
pub const MAX_CONFIG_BYTES: usize = 16 * 1024;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Disabled,
    Observe,
    ProposalExperiment,
}

impl fmt::Display for Mode {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Disabled => formatter.write_str("disabled"),
            Self::Observe => formatter.write_str("observe"),
            Self::ProposalExperiment => formatter.write_str("proposal_experiment"),
        }
    }
}

#[derive(Debug, Clone)]
pub struct Config {
    pub enabled: bool,
    pub mode: Mode,
    pub expected_game_version: String,
    pub serializer_text_offset: usize,
    pub expected_prologue: Vec<u8>,
    pub caller_text_offset: usize,
    pub expected_callsite: Vec<u8>,
    pub reviewed_abi: String,
    pub reviewed_buffer_len: usize,
    pub evidence_reviewed: bool,
    pub offline_test_acknowledged: bool,
    pub capture_offsets: Vec<u8>,
    pub run_label: String,
    pub max_dumps: usize,
    pub poll_global_team_attack: bool,
    pub observe_rule_codec: bool,
    pub observe_rule_application: bool,
}

impl Default for Config {
    fn default() -> Self {
        Self {
            enabled: false,
            mode: Mode::Disabled,
            expected_game_version: SUPPORTED_GAME_VERSION.to_owned(),
            serializer_text_offset: 0,
            expected_prologue: Vec::new(),
            caller_text_offset: 0,
            expected_callsite: Vec::new(),
            reviewed_abi: String::new(),
            reviewed_buffer_len: 0,
            evidence_reviewed: false,
            offline_test_acknowledged: false,
            capture_offsets: Vec::new(),
            run_label: "unlabelled".to_owned(),
            max_dumps: 32,
            poll_global_team_attack: false,
            observe_rule_codec: false,
            observe_rule_application: false,
        }
    }
}

#[derive(Debug)]
pub enum ConfigError {
    Io(String),
    Syntax { line: usize, message: String },
}

impl fmt::Display for ConfigError {
    fn fmt(&self, formatter: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::Io(message) => write!(formatter, "I/O error: {message}"),
            Self::Syntax { line, message } => write!(formatter, "line {line}: {message}"),
        }
    }
}

impl Config {
    pub fn load() -> Result<Option<Self>, ConfigError> {
        let file = match File::open(CONFIG_PATH) {
            Ok(file) => file,
            Err(error) if error.kind() == io::ErrorKind::NotFound => return Ok(None),
            Err(error) => return Err(ConfigError::Io(error.to_string())),
        };

        let mut contents = String::new();
        file.take((MAX_CONFIG_BYTES + 1) as u64)
            .read_to_string(&mut contents)
            .map_err(|error| ConfigError::Io(error.to_string()))?;
        parse(&contents).map(Some)
    }
}

fn syntax(line: usize, message: impl Into<String>) -> ConfigError {
    ConfigError::Syntax {
        line,
        message: message.into(),
    }
}

pub fn parse(contents: &str) -> Result<Config, ConfigError> {
    if contents.len() > MAX_CONFIG_BYTES {
        return Err(syntax(0, "configuration exceeds 16 KiB"));
    }
    let mut config = Config::default();
    let mut seen = BTreeSet::new();

    for (index, raw_line) in contents.lines().enumerate() {
        let line_number = index + 1;
        let line = strip_comment(raw_line).trim();
        if line.is_empty() {
            continue;
        }

        let (raw_key, raw_value) = line
            .split_once('=')
            .ok_or_else(|| syntax(line_number, "expected key = value"))?;
        let key = raw_key.trim();
        let value = raw_value.trim();
        if key.is_empty() || value.is_empty() {
            return Err(syntax(line_number, "key and value must both be present"));
        }
        if !seen.insert(key.to_owned()) {
            return Err(syntax(line_number, format!("duplicate key '{key}'")));
        }

        match key {
            "enabled" => config.enabled = parse_bool(value, line_number)?,
            "mode" => {
                config.mode = match parse_string(value, line_number)? {
                    "disabled" => Mode::Disabled,
                    "observe" => Mode::Observe,
                    "proposal_experiment" => Mode::ProposalExperiment,
                    other => {
                        return Err(syntax(
                            line_number,
                            format!("unsupported mode '{other}'; use 'disabled', 'observe', or 'proposal_experiment'"),
                        ));
                    }
                }
            }
            "expected_game_version" => {
                config.expected_game_version = parse_string(value, line_number)?.to_owned()
            }
            "serializer_text_offset" => {
                config.serializer_text_offset = parse_usize(value, line_number)?
            }
            "expected_prologue" => {
                config.expected_prologue =
                    decode_hex(parse_string(value, line_number)?, line_number)?
            }
            "max_dumps" => config.max_dumps = parse_usize(value, line_number)?,
            "poll_global_team_attack" => {
                config.poll_global_team_attack = parse_bool(value, line_number)?
            }
            "observe_rule_codec" => config.observe_rule_codec = parse_bool(value, line_number)?,
            "observe_rule_application" => {
                config.observe_rule_application = parse_bool(value, line_number)?
            }
            "caller_text_offset" => config.caller_text_offset = parse_usize(value, line_number)?,
            "expected_callsite" => {
                config.expected_callsite =
                    decode_hex(parse_string(value, line_number)?, line_number)?
            }
            "reviewed_abi" => config.reviewed_abi = parse_string(value, line_number)?.to_owned(),
            "reviewed_buffer_len" => config.reviewed_buffer_len = parse_usize(value, line_number)?,
            "evidence_reviewed" => config.evidence_reviewed = parse_bool(value, line_number)?,
            "offline_test_acknowledged" => {
                config.offline_test_acknowledged = parse_bool(value, line_number)?
            }
            "capture_offsets" => {
                config.capture_offsets =
                    decode_hex(parse_string(value, line_number)?, line_number)?;
                let unique: BTreeSet<_> = config.capture_offsets.iter().copied().collect();
                if unique.len() != config.capture_offsets.len() {
                    return Err(syntax(line_number, "capture_offsets contains duplicates"));
                }
                if unique
                    .iter()
                    .any(|offset| !matches!(offset, 0x04..=0x2c | 0x58..=0x5c))
                {
                    return Err(syntax(
                        line_number,
                        "only reviewed rule bytes 04..2C or 58..5C may be captured",
                    ));
                }
            }
            "run_label" => {
                let label = parse_string(value, line_number)?;
                if label.is_empty()
                    || label.len() > 48
                    || !label
                        .bytes()
                        .all(|b| b.is_ascii_alphanumeric() || b == b'_' || b == b'-')
                {
                    return Err(syntax(
                        line_number,
                        "run_label requires 1..48 ASCII letters, digits, underscores, or hyphens",
                    ));
                }
                config.run_label = label.to_owned();
            }
            _ => return Err(syntax(line_number, format!("unknown key '{key}'"))),
        }
    }

    if !(1..=256).contains(&config.max_dumps) {
        return Err(syntax(0, "max_dumps must be between 1 and 256"));
    }

    Ok(config)
}

fn strip_comment(line: &str) -> &str {
    let mut in_quotes = false;
    let mut escaped = false;

    for (index, byte) in line.bytes().enumerate() {
        if escaped {
            escaped = false;
            continue;
        }
        if byte == b'\\' && in_quotes {
            escaped = true;
            continue;
        }
        if byte == b'"' {
            in_quotes = !in_quotes;
        } else if byte == b'#' && !in_quotes {
            return &line[..index];
        }
    }

    line
}

fn parse_bool(value: &str, line: usize) -> Result<bool, ConfigError> {
    match value {
        "true" => Ok(true),
        "false" => Ok(false),
        _ => Err(syntax(line, "expected true or false")),
    }
}

fn parse_string(value: &str, line: usize) -> Result<&str, ConfigError> {
    if value.len() < 2 || !value.starts_with('"') || !value.ends_with('"') {
        return Err(syntax(line, "expected a double-quoted string"));
    }

    let inner = &value[1..value.len() - 1];
    if inner.contains('"') || inner.contains('\\') {
        return Err(syntax(
            line,
            "escapes and embedded quotes are not supported",
        ));
    }
    Ok(inner)
}

fn parse_usize(value: &str, line: usize) -> Result<usize, ConfigError> {
    if value.starts_with('_')
        || value.ends_with('_')
        || value.contains("__")
        || value.starts_with('+')
        || value.starts_with("0x_")
        || value.starts_with("0X_")
    {
        return Err(syntax(line, "invalid integer separator or sign"));
    }
    let compact: String = value
        .chars()
        .filter(|character| *character != '_')
        .collect();
    let parsed = if let Some(hex) = compact
        .strip_prefix("0x")
        .or_else(|| compact.strip_prefix("0X"))
    {
        u64::from_str_radix(hex, 16)
    } else {
        compact.parse::<u64>()
    }
    .map_err(|_| syntax(line, format!("invalid non-negative integer '{value}'")))?;

    usize::try_from(parsed).map_err(|_| syntax(line, "integer does not fit in usize"))
}

fn decode_hex(value: &str, line: usize) -> Result<Vec<u8>, ConfigError> {
    let compact: String = value
        .chars()
        .filter(|character| {
            !character.is_ascii_whitespace() && *character != ':' && *character != '-'
        })
        .collect();

    if !compact.is_ascii() {
        return Err(syntax(
            line,
            "hex signature must contain ASCII hexadecimal characters only",
        ));
    }
    if !compact.len().is_multiple_of(2) {
        return Err(syntax(
            line,
            "hex signature must contain complete byte pairs",
        ));
    }

    (0..compact.len())
        .step_by(2)
        .map(|index| {
            u8::from_str_radix(&compact[index..index + 2], 16)
                .map_err(|_| syntax(line, "hex signature contains a non-hex character"))
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_safe_example_shape() {
        let config = parse(
            r#"
                enabled = true
                mode = "observe"
                expected_game_version = "13.0.5"
                serializer_text_offset = 0x1234
                expected_prologue = "FD 7B BF A9-F3:03:00:AA FD-7B-BF-A9-F3-03-00-AA"
                max_dumps = 12
            "#,
        )
        .unwrap();

        assert!(config.enabled);
        assert_eq!(config.mode, Mode::Observe);
        assert_eq!(config.serializer_text_offset, 0x1234);
        assert_eq!(config.expected_prologue.len(), 16);
        assert_eq!(config.max_dumps, 12);
    }

    #[test]
    fn rejects_unknown_keys() {
        assert!(parse("mutate = true").is_err());
    }

    #[test]
    fn comments_inside_strings_are_not_removed() {
        assert_eq!(
            strip_comment("expected_prologue = \"AA#BB\" # trailing comment"),
            "expected_prologue = \"AA#BB\" "
        );
    }

    #[test]
    fn rejects_non_ascii_hex_without_panicking() {
        assert!(parse("expected_prologue = \"AAA€\"").is_err());
    }

    #[test]
    fn defaults_are_inert() {
        let config = parse("").unwrap();
        assert!(!config.enabled);
        assert_eq!(config.mode, Mode::Disabled);
        assert!(!config.evidence_reviewed);
        assert!(config.capture_offsets.is_empty());
    }

    #[test]
    fn rejects_duplicate_keys_and_unknown_modes() {
        assert!(parse("enabled = true\nenabled = false").is_err());
        assert_eq!(
            parse("mode = \"proposal_experiment\"").unwrap().mode,
            Mode::ProposalExperiment
        );
        assert!(parse("mode = \"mutate\"").is_err());
        assert!(parse("mode = \"observe\" trailing").is_err());
    }

    #[test]
    fn rejects_bad_limits_offsets_and_labels() {
        for input in [
            "max_dumps = 0",
            "max_dumps = 257",
            "max_dumps = -1",
            "max_dumps = _32",
            "max_dumps = 3__2",
            "max_dumps = +32",
            "max_dumps = 0x_20",
            "capture_offsets = \"60\"",
            "capture_offsets = \"04 04\"",
            "run_label = \"../../bad\"",
        ] {
            assert!(parse(input).is_err(), "{input}");
        }
        assert!(parse(&" ".repeat(MAX_CONFIG_BYTES + 1)).is_err());
    }

    #[test]
    fn prepared_batch_profile_enables_independent_observation() {
        let config = parse(include_str!("../config/offline_batch_13_0_5.toml.example")).unwrap();
        crate::validation::validate_config(&config, "13.0.5").unwrap();
        assert!(config.poll_global_team_attack);
        assert_eq!(config.capture_offsets, [0x11]);
        assert_eq!(config.run_label, "OFFLINE_BATCH_01");
    }

    #[test]
    fn shipped_configuration_is_inert() {
        let config = parse(include_str!("../config/quickplay_team_attack.toml.example")).unwrap();
        assert!(!config.enabled);
        assert_eq!(config.mode, Mode::Disabled);
    }

    #[test]
    fn codec_profile_is_bounded_and_keeps_old_profiles_inert() {
        let mut config = parse(include_str!("../config/codec_batch_13_0_5.toml.example")).unwrap();
        assert!(config.observe_rule_codec);
        assert_eq!(config.run_label, "CODEC_OFFLINE_BATCH_01");
        crate::validation::validate_config(&config, "13.0.5").unwrap();
        config.poll_global_team_attack = false;
        assert!(crate::validation::validate_config(&config, "13.0.5").is_err());
        assert!(!parse("").unwrap().observe_rule_codec);
    }

    #[test]
    fn application_profile_requires_bounded_codec_and_defaults_off() {
        let mut c = parse(include_str!(
            "../config/application_batch_13_0_5.toml.example"
        ))
        .unwrap();
        assert!(c.observe_rule_application);
        crate::validation::validate_config(&c, "13.0.5").unwrap();
        c.observe_rule_codec = false;
        assert!(crate::validation::validate_config(&c, "13.0.5").is_err());
        assert!(!parse("").unwrap().observe_rule_application);
    }

    #[test]
    fn proposal_experiment_profile_is_explicit_and_guarded() {
        let c = parse(include_str!(
            "../config/proposal_experiment_13_0_5.toml.example"
        ))
        .unwrap();
        assert_eq!(c.mode, Mode::ProposalExperiment);
        assert!(c.observe_rule_application);
        crate::validation::validate_config(&c, "13.0.5").unwrap();
    }
}
