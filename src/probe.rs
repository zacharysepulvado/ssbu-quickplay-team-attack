//! Switch-only integration; the optional global watcher uses reviewed 13.0.5 data.
use crate::{
    capture::{CaptureStore, CAPTURE_CAPACITY, COMPACT_BUFFER_LEN},
    capture_log::{CaptureLog, LOG_DIR},
    config::Config,
    validation,
    watch::{self, Observation, WatchSchedule},
};
use skyline::{
    hooks::{getRegionAddress, A64HookFunction, Region},
    libc::c_void,
    nn::oe,
};
use std::{
    path::Path,
    ptr,
    sync::atomic::{AtomicBool, AtomicU8, AtomicUsize, Ordering},
    time::Duration,
};

type CompactSerializer = unsafe extern "C" fn(*mut u8);
static ORIGINAL: AtomicUsize = AtomicUsize::new(0);
static INSTALL_ATTEMPTED: AtomicBool = AtomicBool::new(false);
static WRITER_READY: AtomicBool = AtomicBool::new(false);
static MAX_DUMPS: AtomicUsize = AtomicUsize::new(0);
static SERIALIZER_CALLS: AtomicUsize = AtomicUsize::new(0);
static MASK: [AtomicU8; COMPACT_BUFFER_LEN] = [const { AtomicU8::new(0) }; COMPACT_BUFFER_LEN];
static CAPTURES: CaptureStore = CaptureStore::new();

// libnx documents SVC 0x06 and this 40-byte MemoryInfo layout. Querying does
// not read the target address. Only the caller's output structure is written.
#[repr(C)]
#[derive(Default)]
struct MemoryInfo {
    address: u64,
    size: u64,
    memory_type: u32,
    attributes: u32,
    permission: u32,
    ipc_refs: u32,
    device_refs: u32,
    padding: u32,
}

pub(crate) fn validate_table_mapping(address: usize, minimum: usize) -> Result<(), String> {
    let mut info = MemoryInfo::default();
    let result: u64;
    unsafe {
        core::arch::asm!("svc #0x6",
            inlateout("x0") &mut info as *mut MemoryInfo as u64 => result,
            lateout("x1") _, in("x2") address,
            clobber_abi("C"), options(nostack));
    }
    if result as u32 != 0
        || address < minimum
        || (address as u64) < info.address
        || info.address.checked_add(info.size).is_none_or(|end| {
            (address as u64)
                .checked_add(16)
                .is_none_or(|last| last > end)
        })
        || info.permission & 1 == 0
        || info.permission & 4 != 0
        || !matches!(info.memory_type & 0xff, 3 | 4 | 9)
    {
        return Err("codec dispatch table is outside readable non-executable module memory".into());
    }
    Ok(())
}

fn validate_global_mapping(address: usize, data_start: usize) -> Result<(), String> {
    let mut info = MemoryInfo::default();
    let result: u64;
    unsafe {
        core::arch::asm!("svc #0x6",
            inlateout("x0") &mut info as *mut MemoryInfo as u64 => result,
            lateout("x1") _, in("x2") address,
            clobber_abi("C"), options(nostack));
    }
    if result as u32 != 0 {
        return Err(format!(
            "QueryMemory for global watcher failed: {:#x}",
            result as u32
        ));
    }
    watch::validate_mapping(
        address,
        data_start,
        info.address,
        info.size,
        info.memory_type,
        info.permission,
    )
    .map_err(str::to_owned)
}

/// One machine-byte load from validated permanent module data. Game writes
/// can occur concurrently, so create no Rust reference and assume no stability.
/// This is a sampled value, never an atomic snapshot of game state.
unsafe fn read_game_byte(address: usize) -> u8 {
    let value: u32;
    unsafe {
        core::arch::asm!("ldrb {value:w}, [{address}]", value = out(reg) value,
            address = in(reg) address, options(nostack, readonly, preserves_flags));
    }
    value as u8
}

fn live_version() -> Result<String, String> {
    let mut version = oe::DisplayVersion { name: [0; 16] };
    unsafe {
        oe::GetDisplayVersion(&mut version);
    }
    let bytes: Vec<u8> = version
        .name
        .iter()
        .copied()
        .take_while(|byte| *byte != 0)
        .collect();
    if bytes.len() == version.name.len() {
        return Err("runtime display version is not terminated".into());
    }
    String::from_utf8(bytes).map_err(|_| "invalid runtime version encoding".into())
}

pub fn install(config: Config) -> Result<(), String> {
    if INSTALL_ATTEMPTED.swap(true, Ordering::AcqRel) {
        return Err("installation already attempted; hot reload is unsupported".into());
    }
    let version = live_version()?;
    validation::validate_config(&config, &version)?;
    let text_address = unsafe { getRegionAddress(Region::Text) as usize };
    let rodata_address = unsafe { getRegionAddress(Region::Rodata) as usize };
    let text_len = validation::validate_region(text_address, rodata_address)?;
    // Skyline supplies mapped module boundaries. Bounds/size were checked above.
    let text = unsafe { std::slice::from_raw_parts(text_address as *const u8, text_len) };
    validation::validate_signatures(&config, text)?;
    let observe_codec = config.observe_rule_codec;
    let observe_application = config.observe_rule_application;
    if observe_application {
        crate::application::validate(text)?;
        let table = text_address
            .checked_add(0x44f3b48)
            .ok_or("receive table overflow")?;
        validate_table_mapping(table, rodata_address)?;
        let entry = unsafe { std::slice::from_raw_parts(table as *const u8, 4) };
        crate::application::validate_receive_table(entry, 0x44f3b48)?;
        let data_start = unsafe { getRegionAddress(Region::Data) as usize };
        let mode = text_address
            .checked_add(crate::application::MODE_OFFSET)
            .ok_or("mode overflow")?;
        validate_global_mapping(mode, data_start)?;
        validate_global_mapping(mode + 3, data_start)?;
    }
    if observe_codec {
        crate::codec_probe::validate(text, text_address, rodata_address)?;
    }
    let global_addresses = if config.poll_global_team_attack {
        if !text_address.is_multiple_of(4096) {
            return Err("global watcher requires page-aligned module text".into());
        }
        watch::validate_source(&config, text)?;
        let data_start = unsafe { getRegionAddress(Region::Data) as usize };
        let global = text_address
            .checked_add(watch::GLOBAL_OFFSET)
            .ok_or("global overflow")?;
        let guard = text_address
            .checked_add(watch::GUARD_OFFSET)
            .ok_or("guard overflow")?;
        validate_global_mapping(global, data_start)?;
        validate_global_mapping(guard, data_start)?;
        Some((global, guard))
    } else {
        None
    };

    let (mut log, path) = CaptureLog::create(Path::new(LOG_DIR), &config)
        .map_err(|error| format!("Create/flush capture log at {LOG_DIR}: {error}"))?;
    log.status("log_ready_before_hook")
        .map_err(|error| format!("Write startup status: {error}"))?;
    if observe_codec {
        log.status("codec_full_bodies_and_dispatch_table_verified")
            .map_err(|error| error.to_string())?;
        log.status("codec_private_selftest_before_hooks_started")
            .map_err(|error| error.to_string())?;
        let calls = crate::codec_probe::native_self_test(text_address).map_err(|error| {
            let _ = log.status(&format!(
                "codec_private_selftest_before_hooks_FAIL: {error}"
            ));
            error
        })?;
        log.status(&format!("codec_private_selftest_before_hooks_PASS: calls:{calls} roundtrips:128 decode_flag_values:256"))
            .map_err(|error| error.to_string())?;
        crate::codec_probe::install(text_address);
        // Test entry -> replacement -> relocated original using only our own
        // buffers. ACTIVE is false, excluding all synthetic calls from live data.
        match crate::codec_probe::native_self_test(text_address) {
            Ok(calls) => {
                if log.status(&format!("codec_private_selftest_after_hooks_PASS: calls:{calls} roundtrips:128 decode_flag_values:256")).is_err() {
                    std::process::abort();
                }
            }
            Err(error) => {
                let _ = log.status(&format!("codec_private_selftest_after_hooks_FAIL: {error}"));
                std::process::abort();
            }
        }
    }
    if observe_application {
        log.status("application_bodies_verified_installing_eight_passive_inline_sites")
            .map_err(|e| e.to_string())?;
        crate::application_probe::install(text_address, config.mode);
        if log
            .status("application_eight_sites_installed_single_instruction_patches_verified")
            .is_err()
        {
            std::process::abort();
        }
    }
    let start_tick = unsafe { skyline::nn::os::GetSystemTick() };
    for &offset in &config.capture_offsets {
        MASK[offset as usize].store(1, Ordering::Relaxed);
    }
    MAX_DUMPS.store(config.max_dumps, Ordering::Relaxed);
    // A ready writer must exist before the hook can capture. On write failure,
    // observing stops; the original function continues unchanged.
    WRITER_READY.store(true, Ordering::Release);
    if let Err(error) = std::thread::Builder::new()
        .name("team-attack-captures".into())
        .stack_size(0x10_000)
        .spawn(move || {
            let mut installation_recorded = false;
            let mut schedule = WatchSchedule::default();
            let mut stored_dumps = 0;
            let mut last_codec = None;
            let mut last_codec_ms = 0;
            let mut last_application = None;
            let mut last_application_ms = 0;
            loop {
                std::thread::sleep(Duration::from_millis(250));
                // Subtract before converting to avoid overflow on long uptime.
                let elapsed_ms =
                    unsafe { skyline::nn::os::GetSystemTick() }.wrapping_sub(start_tick) / 19_200;
                if !installation_recorded && ORIGINAL.load(Ordering::Acquire) != 0 {
                    if log.status("hook_installed").is_err() {
                        WRITER_READY.store(false, Ordering::Release);
                        crate::codec_probe::stop();
                        crate::application_probe::stop();
                        skyline::println!(
                            "[team-attack] startup status write failed; capture stopped\n"
                        );
                        return;
                    }
                    installation_recorded = true;
                }
                if global_addresses.is_some() && elapsed_ms >= watch::WATCH_LIMIT_MS {
                    WRITER_READY.store(false, Ordering::Release);
                        crate::codec_probe::stop();
                        crate::application_probe::stop();
                    let _ = log.status("watch_limit_reached_20_minutes_observation_stopped");
                    return;
                }
                let mut dirty = false;
                if observe_codec {
                    match crate::codec_probe::drain(&mut log) {
                        Ok(written) => dirty |= written,
                        Err(_) => {
                            WRITER_READY.store(false, Ordering::Release);
                        crate::codec_probe::stop();
                        crate::application_probe::stop();
                            return;
                        }
                    }
                    let counts = crate::codec_probe::counts();
                    if last_codec != Some(counts) || elapsed_ms.saturating_sub(last_codec_ms) >= 5000 {
                        if log.event(&format!("codec_counts: elapsed_ms:{elapsed_ms} encode:{} decode:{} dropped:{}", counts.0, counts.1, counts.2)).is_err() {
                            WRITER_READY.store(false, Ordering::Release);
                        crate::codec_probe::stop();
                        crate::application_probe::stop();
                            return;
                        }
                        last_codec = Some(counts);
                        last_codec_ms = elapsed_ms;
                        dirty = true;
                    }
                }
                if observe_application {
                    match crate::application_probe::drain(&mut log) {
                        Ok(written) => dirty |= written,
                        Err(_) => {WRITER_READY.store(false, Ordering::Release);crate::codec_probe::stop();crate::application_probe::stop();return;}
                    }
                    let counts = crate::application_probe::counts();
                    if last_application != Some(counts) || elapsed_ms.saturating_sub(last_application_ms) >= 5000 {
                        if log.event(&format!("application_counts: elapsed_ms:{elapsed_ms} local:{} participant:{} ready:{} before:{} after:{} submit:{} receive:{} stored:{} dropped:{}", counts.0[0],counts.0[1],counts.0[2],counts.0[3],counts.0[4],counts.0[5],counts.0[6],counts.0[7],counts.1)).is_err() {
                            WRITER_READY.store(false, Ordering::Release);crate::codec_probe::stop();crate::application_probe::stop();return;
                        }
                        last_application=Some(counts);last_application_ms=elapsed_ms;dirty=true;
                    }
                }
                for index in 0..CAPTURE_CAPACITY {
                    if let Some(capture) = CAPTURES.take(index) {
                        if log
                            .dump_written(capture.sequence, elapsed_ms)
                            .and_then(|_| log.append(&capture))
                            .is_err()
                        {
                            WRITER_READY.store(false, Ordering::Release);
                        crate::codec_probe::stop();
                        crate::application_probe::stop();
                            skyline::println!("[team-attack] write failed; capture stopped\n");
                            return;
                        }
                        stored_dumps += 1;
                        dirty = true;
                    }
                }
                if let Some((global, guard)) = global_addresses {
                    let initialized = unsafe { read_game_byte(guard) } & 1 != 0;
                    let value = if initialized {
                        Some(unsafe { read_game_byte(global) })
                    } else {
                        None
                    };
                    let state = Observation {
                        initialized,
                        value,
                        serializer_calls: SERIALIZER_CALLS.load(Ordering::Relaxed),
                        stored_dumps,
                    };
                    if schedule.should_log(elapsed_ms, state) {
                        if log.watch(elapsed_ms, state).is_err() {
                            WRITER_READY.store(false, Ordering::Release);
                        crate::codec_probe::stop();
                        crate::application_probe::stop();
                            skyline::println!(
                                "[team-attack] global watch write failed; capture stopped\n"
                            );
                            return;
                        }
                        dirty = true;
                    }
                }
                if dirty && log.flush().is_err() {
                    WRITER_READY.store(false, Ordering::Release);
                        crate::codec_probe::stop();
                        crate::application_probe::stop();
                    skyline::println!("[team-attack] flush failed; capture stopped\n");
                    return;
                }
            }
        })
    {
        WRITER_READY.store(false, Ordering::Release);
                        crate::codec_probe::stop();
                        crate::application_probe::stop();
        return Err(format!("writer could not start: {error}"));
    }

    let target = (text_address + config.serializer_text_offset) as *const c_void;
    let mut trampoline = ptr::null_mut();
    // Startup only. Skyline cannot atomically publish our Rust pointer together
    // with its code patch, and does not expose transactional rollback here.
    unsafe {
        A64HookFunction(
            target,
            compact_serializer_observer as *const c_void,
            &mut trampoline,
        );
    }
    if trampoline.is_null() {
        // Code may already have changed: returning success or silently skipping
        // the original could corrupt game state. This is an explicit fail-stop.
        std::process::abort();
    }
    ORIGINAL.store(trampoline as usize, Ordering::Release);
    if observe_codec && WRITER_READY.load(Ordering::Acquire) {
        crate::codec_probe::start(start_tick);
    }
    if observe_application && WRITER_READY.load(Ordering::Acquire) {
        crate::application_probe::start(start_tick);
    }
    skyline::println!(
        "[team-attack] observer installed for {version}; log {}\n",
        path.display()
    );
    Ok(())
}

unsafe extern "C" fn compact_serializer_observer(buffer: *mut u8) {
    let address = ORIGINAL.load(Ordering::Acquire);
    if address == 0 {
        // Unexpected invocation during installation cannot safely continue.
        // No waiting, panic formatting, or silent omission of the original.
        std::process::abort();
    }
    let original: CompactSerializer = unsafe { std::mem::transmute(address) };
    SERIALIZER_CALLS.fetch_add(1, Ordering::Relaxed);
    unsafe {
        original(buffer);
    }
    if buffer.is_null() || !WRITER_READY.load(Ordering::Acquire) {
        return;
    }

    CAPTURES.try_capture(MAX_DUMPS.load(Ordering::Relaxed), || {
        let mut bytes = [0; COMPACT_BUFFER_LEN];
        for (offset, (byte, selected)) in bytes.iter_mut().zip(MASK.iter()).enumerate() {
            if selected.load(Ordering::Relaxed) != 0 {
                // SAFETY obligation: the reviewer must prove this initialized
                // output byte remains readable after the original returns.
                *byte = unsafe { ptr::read(buffer.add(offset)) };
            }
        }
        bytes
    });
}
