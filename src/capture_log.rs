//! All file I/O runs during initialization or on the writer thread.
use crate::{
    capture::{Capture, COMPACT_BUFFER_LEN},
    config::Config,
};
use std::{
    fs::{self, File, OpenOptions},
    io::{self, BufWriter, Write},
    path::{Path, PathBuf},
};

pub const LOG_DIR: &str = "sd:/ultimate/quickplay_team_attack/captures";

/// Reserve a new name without replacing an earlier session.
/// The pinned Skyline std fork does not implement create_new by itself:
/// GetEntryType(NotFound) only creates when the separate `create` flag is set.
/// Its combined create/create_new path also ignores CreateFile's result.
/// Call the native exclusive creation API and check its result on Switch.
#[cfg(target_os = "switch")]
fn create_capture_file(path: &Path) -> io::Result<File> {
    use std::ffi::CString;
    let path_text = path
        .to_str()
        .ok_or_else(|| io::Error::new(io::ErrorKind::InvalidInput, "capture path is not UTF-8"))?;
    let native_path = CString::new(path_text)
        .map_err(|_| io::Error::new(io::ErrorKind::InvalidInput, "NUL in capture path"))?;
    // CreateFile fails with PathAlreadyExists; it does not open/truncate an
    // existing file. Do not proceed to OpenFile unless this reservation succeeds.
    let result = unsafe { skyline::nn::fs::CreateFile(native_path.as_ptr().cast(), 0) };
    check_create_result(result)?;
    OpenOptions::new().write(true).open(path)
}

#[cfg(not(target_os = "switch"))]
fn create_capture_file(path: &Path) -> io::Result<File> {
    OpenOptions::new().write(true).create_new(true).open(path)
}

#[cfg(any(target_os = "switch", test))]
fn check_create_result(result: u32) -> io::Result<()> {
    match result {
        0 => Ok(()),
        0x402 => Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "capture already exists",
        )),
        0x202 => Err(io::Error::new(
            io::ErrorKind::NotFound,
            "capture directory not found",
        )),
        other => Err(io::Error::from_raw_os_error(other as i32)),
    }
}

pub struct CaptureLog {
    writer: BufWriter<File>,
    mask: [bool; COMPACT_BUFFER_LEN],
}

impl CaptureLog {
    pub fn create(directory: &Path, config: &Config) -> io::Result<(Self, PathBuf)> {
        fs::create_dir_all(directory)?;
        // Exclusive creation never truncates an earlier session.
        for session in 0..10_000 {
            let path = directory.join(format!("capture-{session:04}.log"));
            match create_capture_file(&path) {
                Ok(file) => {
                    let mut writer = BufWriter::new(file);
                    write_header(&mut writer, config)?;
                    writer.flush()?;
                    writer.get_ref().sync_all()?;
                    let mut mask = [false; COMPACT_BUFFER_LEN];
                    for &offset in &config.capture_offsets {
                        let byte = mask.get_mut(offset as usize).ok_or_else(|| {
                            io::Error::new(io::ErrorKind::InvalidInput, "invalid capture offset")
                        })?;
                        *byte = true;
                    }
                    return Ok((Self { writer, mask }, path));
                }
                Err(error) if error.kind() == io::ErrorKind::AlreadyExists => continue,
                Err(error) => return Err(error),
            }
        }
        Err(io::Error::new(
            io::ErrorKind::AlreadyExists,
            "capture directory has 10,000 sessions; archive them first",
        ))
    }

    pub fn append(&mut self, capture: &Capture) -> io::Result<()> {
        write_capture(&mut self.writer, &self.mask, capture)
    }

    pub fn flush(&mut self) -> io::Result<()> {
        self.writer.flush()?;
        self.writer.get_ref().sync_all()
    }

    pub fn event(&mut self, message: &str) -> io::Result<()> {
        writeln!(self.writer, "# {message}")
    }

    pub fn status(&mut self, message: &str) -> io::Result<()> {
        // Event comments, not metadata keys: repeated state transitions must
        // remain compatible with the strict reader's duplicate-header checks.
        writeln!(self.writer, "# observer_status: {message}")?;
        self.flush()
    }

    pub fn watch(&mut self, elapsed_ms: u64, state: crate::watch::Observation) -> io::Result<()> {
        let value = state
            .value
            .map_or_else(|| "--".to_owned(), |v| format!("{v:02X}"));
        // Comment events use colons only; existing dump tools ignore them.
        writeln!(self.writer,
            "# watch: elapsed_ms:{} initialized:{} team_attack_global:{} serializer_calls:{} stored_dumps:{}",
            elapsed_ms, u8::from(state.initialized), value, state.serializer_calls, state.stored_dumps)
    }

    pub fn dump_written(&mut self, sequence: usize, elapsed_ms: u64) -> io::Result<()> {
        writeln!(
            self.writer,
            "# dump_written: sequence:{sequence} elapsed_ms:{elapsed_ms}"
        )
    }
}

pub fn write_header(writer: &mut impl Write, config: &Config) -> io::Result<()> {
    writeln!(writer, "# observer_version={}", env!("CARGO_PKG_VERSION"))?;
    writeln!(writer, "# run_label={}", config.run_label)?;
    writeln!(writer, "# observe_rule_codec={}", config.observe_rule_codec)?;
    writeln!(
        writer,
        "# poll_global_team_attack={}",
        config.poll_global_team_attack
    )?;
    if config.poll_global_team_attack {
        writeln!(writer, "# global_text_offset=0x530a981")?;
        writeln!(writer, "# global_init_guard_text_offset=0x53144d8")?;
        writeln!(writer, "# global_poll_interval_ms=250")?;
        writeln!(writer, "# watch_heartbeat_ms=5000")?;
        writeln!(writer, "# watch_limit_ms=1200000")?;
    }
    writeln!(
        writer,
        "# observe_rule_application={}",
        config.observe_rule_application
    )?;
    writeln!(writer, "# game_version={}", config.expected_game_version)?;
    writeln!(
        writer,
        "# serializer_text_offset={:#x}",
        config.serializer_text_offset
    )?;
    writeln!(
        writer,
        "# caller_text_offset={:#x}",
        config.caller_text_offset
    )?;
    writeln!(writer, "# compact_buffer_length=0x69")?;
    writeln!(writer, "# reviewed_abi={}", config.reviewed_abi)?;
    for (key, signature) in [
        ("entry_signature", &config.expected_prologue),
        ("caller_signature", &config.expected_callsite),
    ] {
        write!(writer, "# {key}=")?;
        for byte in signature {
            write!(writer, "{byte:02X}")?;
        }
        writeln!(writer)?;
    }
    writeln!(
        writer,
        "# format: dump <sequence>: 105 hex bytes or -- for unread bytes"
    )
}

pub fn write_capture(
    writer: &mut impl Write,
    mask: &[bool; COMPACT_BUFFER_LEN],
    capture: &Capture,
) -> io::Result<()> {
    write!(writer, "dump {:04}:", capture.sequence)?;
    for (byte, include) in capture.bytes.iter().zip(mask) {
        if *include {
            write!(writer, " {byte:02X}")?;
        } else {
            write!(writer, " --")?;
        }
    }
    writeln!(writer)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn native_creation_failure_never_reports_success() {
        assert!(check_create_result(0).is_ok());
        assert_eq!(
            check_create_result(0x402).unwrap_err().kind(),
            io::ErrorKind::AlreadyExists
        );
        assert_eq!(
            check_create_result(0x202).unwrap_err().kind(),
            io::ErrorKind::NotFound
        );
        assert_eq!(
            check_create_result(0xdead).unwrap_err().raw_os_error(),
            Some(0xdead)
        );
    }

    #[test]
    fn startup_writes_header_without_samples_and_preserves_previous_session() {
        let directory = std::env::temp_dir().join(format!("ssbu-log-test-{}", std::process::id()));
        fs::create_dir(&directory).unwrap();
        let old = directory.join("capture-0000.log");
        fs::write(&old, "prior session: do not overwrite\n").unwrap();
        let config = Config {
            capture_offsets: vec![0x11],
            ..Config::default()
        };
        let (mut log, path) = CaptureLog::create(&directory, &config).unwrap();
        assert_eq!(path.file_name().unwrap(), "capture-0001.log");
        // Read before dropping/flushing the log again: header is durable on create.
        let header = fs::read_to_string(&path).unwrap();
        assert!(header.contains(concat!(
            "# observer_version=",
            env!("CARGO_PKG_VERSION"),
            "\n"
        )));
        assert!(!header.lines().any(|line| line.starts_with("dump ")));
        log.status("hook_installed").unwrap();
        assert!(fs::read_to_string(&path)
            .unwrap()
            .contains("# observer_status: hook_installed\n"));
        assert_eq!(
            fs::read_to_string(&old).unwrap(),
            "prior session: do not overwrite\n"
        );
        drop(log);
        fs::remove_dir_all(directory).unwrap();
    }

    #[test]
    fn header_retains_exact_code_identity() {
        let config = Config {
            expected_prologue: vec![0xaa, 0x00],
            expected_callsite: vec![0x94, 0xff],
            reviewed_abi: "void_u8_ptr_v1".into(),
            ..Config::default()
        };
        let mut output = Vec::new();
        write_header(&mut output, &config).unwrap();
        let header = String::from_utf8(output).unwrap();
        assert!(header.contains("# entry_signature=AA00\n"));
        assert!(header.contains("# caller_signature=94FF\n"));
        assert!(header.contains("# reviewed_abi=void_u8_ptr_v1\n"));
    }

    #[test]
    fn excluded_bytes_are_never_serialized() {
        let mut mask = [false; COMPACT_BUFFER_LEN];
        mask[4] = true;
        let capture = Capture {
            sequence: 2,
            bytes: [0xab; COMPACT_BUFFER_LEN],
        };
        let mut output = Vec::new();
        write_capture(&mut output, &mask, &capture).unwrap();
        let line = String::from_utf8(output).unwrap();
        assert_eq!(line.matches("AB").count(), 1);
        assert_eq!(line.matches("--").count(), 104);
        assert!(line.starts_with("dump 0002:"));
    }
}
