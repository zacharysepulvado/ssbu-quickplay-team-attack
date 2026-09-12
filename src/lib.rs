#![deny(unsafe_op_in_unsafe_fn)]

pub mod application;
pub mod capture;
pub mod capture_log;
pub mod codec;
pub mod config;
pub mod validation;
pub mod watch;

#[cfg(target_os = "switch")]
mod probe;

#[cfg(target_os = "switch")]
mod application_probe;
#[cfg(target_os = "switch")]
mod codec_bytes;
#[cfg(target_os = "switch")]
mod codec_probe;

#[cfg(target_os = "switch")]
#[skyline::main(name = "quickplay_team_attack_probe")]
pub fn main() {
    skyline::println!("[team-attack] guarded proposal experiment 0.3.0\n");
    let config = match config::Config::load() {
        Ok(Some(config)) => config,
        Ok(None) => {
            skyline::println!("[team-attack] no configuration; no hook installed\n");
            return;
        }
        Err(error) => {
            skyline::println!("[team-attack] configuration rejected: {error}; no hook installed\n");
            startup_error(&format!("Configuration: {error}"));
            return;
        }
    };
    if !config.enabled || config.mode == config::Mode::Disabled {
        skyline::println!("[team-attack] disabled; no hook installed\n");
        return;
    }
    if let Err(error) = probe::install(config) {
        skyline::println!("[team-attack] observer refused: {error}; recording stopped\n");
        startup_error(&error);
    }
}

#[cfg(target_os = "switch")]
fn startup_error(error: &str) {
    // skyline 0.6.0's show_error expects the caller to supply NUL termination.
    // Keep well below its byte-truncation branch (which can split UTF-8).
    let detail: String = error.chars().filter(|c| *c != '\0').take(300).collect();
    skyline::error::show_error(
        70,
        "Team Attack experiment 0.3.0 could not start.\0",
        &format!("{detail}\n\nRecording did not start. Photograph this message and its Details. No match test is needed.\0"),
    );
}
