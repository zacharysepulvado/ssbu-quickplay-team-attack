//! Passive leaf codec hooks. No game rule or packet writes are performed here.
use crate::{
    capture::{CaptureStore, CAPTURE_CAPACITY},
    capture_log::CaptureLog,
    codec::{self, CodecFn, Cursor, Descriptor},
    codec_bytes,
};
use skyline::{hooks::A64HookFunction, libc::c_void};
use std::{
    io, ptr,
    sync::atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering},
};

static ENCODER: AtomicUsize = AtomicUsize::new(0);
static DECODER: AtomicUsize = AtomicUsize::new(0);
static ACTIVE: AtomicBool = AtomicBool::new(false);
static START_TICK: AtomicU64 = AtomicU64::new(0);
static CALLS: [AtomicUsize; 2] = [const { AtomicUsize::new(0) }; 2];
static DROPPED: AtomicUsize = AtomicUsize::new(0);
static EVENTS: CaptureStore = CaptureStore::new();

pub fn validate(text: &[u8], base: usize, rodata: usize) -> Result<(), String> {
    for (offset, expected) in [
        (codec::ENCODER_OFFSET, codec_bytes::ENCODER),
        (codec::DECODER_OFFSET, codec_bytes::DECODER),
    ] {
        if text.get(offset..offset + expected.len()) != Some(expected) {
            return Err(format!("complete codec body mismatch at main+{offset:#x}; no native self-test or codec hooks"));
        }
    }
    let table = base
        .checked_add(codec::TABLE_OFFSET)
        .ok_or("codec table overflow")?;
    crate::probe::validate_table_mapping(table, rodata)?;
    // Relocated dispatch pointers in kernel-validated module memory.
    let encode = unsafe { ptr::read_unaligned(table as *const usize) };
    let decode = unsafe { ptr::read_unaligned((table + 8) as *const usize) };
    if encode != base + codec::ENCODER_OFFSET || decode != base + codec::DECODER_OFFSET {
        return Err("codec dispatch pointers do not match reviewed entries".into());
    }
    Ok(())
}

pub fn native_self_test(base: usize) -> Result<usize, String> {
    // Caller must have validated the complete mapped code and descriptor table.
    let encoder: CodecFn = unsafe { std::mem::transmute(base + codec::ENCODER_OFFSET) };
    let decoder: CodecFn = unsafe { std::mem::transmute(base + codec::DECODER_OFFSET) };
    unsafe { codec::self_test(encoder, decoder) }
}

pub fn install(base: usize) {
    for (offset, replacement, original) in [
        (
            codec::ENCODER_OFFSET,
            encoder_hook as *const c_void,
            &ENCODER,
        ),
        (
            codec::DECODER_OFFSET,
            decoder_hook as *const c_void,
            &DECODER,
        ),
    ] {
        let mut trampoline = ptr::null_mut();
        unsafe {
            A64HookFunction(
                (base + offset) as *const c_void,
                replacement,
                &mut trampoline,
            );
        }
        if trampoline.is_null() {
            std::process::abort();
        }
        original.store(trampoline as usize, Ordering::Release);
    }
}

pub fn start(start_tick: u64) {
    START_TICK.store(start_tick, Ordering::Relaxed);
    ACTIVE.store(true, Ordering::Release);
}

pub fn stop() {
    ACTIVE.store(false, Ordering::Release);
}

unsafe fn load_position(cursor: *mut Cursor) -> u32 {
    let value: u32;
    unsafe {
        core::arch::asm!("ldr {value:w}, [{address}, #12]", value = out(reg) value,
        address = in(reg) cursor, options(nostack, readonly, preserves_flags));
    }
    value
}

unsafe fn rule_values(desc: *mut Descriptor) -> (u8, u8) {
    let address: usize;
    let base: u32;
    let team: u32;
    // Both complete leaf bodies access descriptor+8 and rule+9/+13. The
    // original does not free them. Use machine reads without Rust references.
    unsafe {
        core::arch::asm!("ldr {address}, [{desc}, #8]", address = out(reg) address,
            desc = in(reg) desc, options(nostack, readonly, preserves_flags));
        core::arch::asm!("ldrb {base:w}, [{address}, #9]", "ldrb {team:w}, [{address}, #13]",
            base = out(reg) base, team = out(reg) team, address = in(reg) address,
            options(nostack, readonly, preserves_flags));
    }
    (base as u8, team as u8)
}

unsafe fn observe(kind: usize, desc: *mut Descriptor, cursor: *mut Cursor) -> usize {
    let address = if kind == 0 { &ENCODER } else { &DECODER }.load(Ordering::Acquire);
    if address == 0 {
        std::process::abort();
    }
    let original: CodecFn = unsafe { std::mem::transmute(address) };
    let active = ACTIVE.load(Ordering::Acquire);
    let before = if active {
        unsafe { load_position(cursor) }
    } else {
        0
    };
    // Preserve original arguments, exactly one original invocation, and x0.
    let result = unsafe { original(desc, cursor) };
    if active && ACTIVE.load(Ordering::Acquire) {
        CALLS[kind].fetch_add(1, Ordering::Relaxed);
        if !EVENTS.try_capture(CAPTURE_CAPACITY, || {
            let (base, team) = unsafe { rule_values(desc) };
            let after = unsafe { load_position(cursor) };
            let elapsed = unsafe { skyline::nn::os::GetSystemTick() }
                .wrapping_sub(START_TICK.load(Ordering::Relaxed))
                / 19_200;
            let mut bytes = [0; crate::capture::COMPACT_BUFFER_LEN];
            bytes[0] = kind as u8;
            bytes[1] = base;
            bytes[2] = team;
            bytes[4..8].copy_from_slice(&before.to_le_bytes());
            bytes[8..12].copy_from_slice(&after.to_le_bytes());
            bytes[12..20].copy_from_slice(&elapsed.to_le_bytes());
            bytes
        }) {
            DROPPED.fetch_add(1, Ordering::Relaxed);
        }
    }
    result
}

unsafe extern "C" fn encoder_hook(desc: *mut Descriptor, cursor: *mut Cursor) -> usize {
    unsafe { observe(0, desc, cursor) }
}
unsafe extern "C" fn decoder_hook(desc: *mut Descriptor, cursor: *mut Cursor) -> usize {
    unsafe { observe(1, desc, cursor) }
}

pub fn counts() -> (usize, usize, usize) {
    (
        CALLS[0].load(Ordering::Relaxed),
        CALLS[1].load(Ordering::Relaxed),
        DROPPED.load(Ordering::Relaxed),
    )
}

pub fn drain(log: &mut CaptureLog) -> io::Result<bool> {
    let mut dirty = false;
    for i in 0..CAPTURE_CAPACITY {
        if let Some(event) = EVENTS.take(i) {
            let b = event.bytes;
            let before = u32::from_le_bytes(b[4..8].try_into().unwrap());
            let after = u32::from_le_bytes(b[8..12].try_into().unwrap());
            let elapsed = u64::from_le_bytes(b[12..20].try_into().unwrap());
            log.event(&format!("codec_event: sequence:{} elapsed_ms:{} direction:{} base_flag:{:02X} team_attack:{:02X} cursor_before:{} cursor_after:{} advanced_14:{}",
                event.sequence, elapsed, if b[0] == 0 { "encode" } else { "decode" }, b[1], b[2], before, after,
                u8::from(after.checked_sub(before) == Some(14))))?;
            dirty = true;
        }
    }
    Ok(dirty)
}
