//! Eight passive inline observations on reviewed MOV instructions. x16/x17 and
//! NZCV are dead at these sites; the callback never modifies InlineCtx or game
//! memory. Original instructions and control flow run through Skyline trampolines.
use crate::{
    application::{self, Event},
    capture::CaptureStore,
    capture_log::CaptureLog,
    config::Mode,
    watch,
};
use skyline::{
    hooks::{A64InlineHook, InlineCtx},
    libc::c_void,
};
use std::{
    io,
    sync::atomic::{AtomicBool, AtomicU64, AtomicUsize, Ordering},
};

static ACTIVE: AtomicBool = AtomicBool::new(false);
static BASE: AtomicUsize = AtomicUsize::new(0);
static START: AtomicU64 = AtomicU64::new(0);
static CALLS: [AtomicUsize; application::SITE_COUNT] =
    [const { AtomicUsize::new(0) }; application::SITE_COUNT];
static DROPPED: AtomicUsize = AtomicUsize::new(0);
static EXPERIMENT: AtomicBool = AtomicBool::new(false);
// Runtime-only guard. This address is never retained in a capture event.
static ARMED_SESSION: AtomicUsize = AtomicUsize::new(0);
// Separate budgets keep offline activity and frequently called sites from
// consuming the co-op application samples. At most 1024 events per boot.
static EVENTS: [CaptureStore; application::SITE_COUNT * 2] =
    [const { CaptureStore::new() }; application::SITE_COUNT * 2];

unsafe fn byte(a: usize) -> u8 {
    let v: u32;
    unsafe {
        core::arch::asm!("ldrb {v:w}, [{a}]", v=out(reg)v,a=in(reg)a,options(nostack,readonly,preserves_flags));
    }
    v as u8
}
unsafe fn word(a: usize) -> u32 {
    let v: u32;
    unsafe {
        core::arch::asm!("ldr {v:w}, [{a}]",v=out(reg)v,a=in(reg)a,options(nostack,readonly,preserves_flags));
    }
    v
}
unsafe fn pointer(a: usize) -> usize {
    let v: usize;
    unsafe {
        core::arch::asm!("ldr {v}, [{a}]",v=out(reg)v,a=in(reg)a,options(nostack,readonly,preserves_flags));
    }
    v
}

unsafe fn write_byte(a: usize, value: u8) {
    unsafe {
        core::arch::asm!(
            "strb {value:w}, [{a}]",
            value = in(reg) u32::from(value),
            a = in(reg) a,
            options(nostack, preserves_flags)
        );
    }
}

unsafe fn local_slot(session: usize) -> u8 {
    let identity = unsafe { pointer(session + 0x9ff8) };
    let manager = session + 0xa010;
    let entries = std::array::from_fn(|slot| unsafe { pointer(manager + 8 + slot * 0x78) });
    application::identity_slot(identity, &entries).unwrap_or(0xff)
}

/// Change only the reviewed local B4 proposal and, if that proposal was armed,
/// its local-copy source. Participant-copy selections never enter this path.
unsafe fn mutate_if_guarded(kind: usize, ctx: &InlineCtx) -> u8 {
    if !EXPERIMENT.load(Ordering::Acquire) {
        return 0xff;
    }
    let base = BASE.load(Ordering::Relaxed);
    if unsafe { word(base + application::MODE_OFFSET) } != application::COOP_MODE {
        return 0xff;
    }
    let session = match kind {
        0 => ctx.registers[24].x() as usize,
        5 => ctx.registers[0].x() as usize,
        _ => return 0xff,
    };
    if session == 0
        || unsafe { word(session + application::SESSION_REQUEST) } != 2
        || unsafe { byte(session + application::SESSION_PREPARED) } != 0
        || unsafe { byte(base + watch::GUARD_OFFSET) } & 1 == 0
        || unsafe { byte(base + watch::GLOBAL_OFFSET) } != 0
    {
        return 0xff;
    }
    let local = unsafe { local_slot(session) };
    if local >= 16 {
        return 0xff;
    }

    if kind == 5 {
        if ctx.registers[1].x() as u16 != 0xb4
            || ctx.registers[3].x() as u32 != 0xd0
            || ctx.registers[2].x() == 0
        {
            return 0xff;
        }
        let proposal = ctx.registers[2].x() as usize;
        if !application::proposal_guard(
            unsafe { word(base + application::MODE_OFFSET) },
            unsafe { word(session + application::SESSION_REQUEST) },
            unsafe { byte(session + application::SESSION_PREPARED) },
            unsafe { byte(base + watch::GUARD_OFFSET) } & 1 != 0,
            unsafe { byte(base + watch::GLOBAL_OFFSET) },
            local,
            unsafe { byte(proposal + 0xc8) },
            unsafe { byte(proposal + 0x11) },
            application::submit_origin((ctx.registers[30].x() as usize).wrapping_sub(base)),
        ) {
            return 0xff;
        }
        unsafe { write_byte(proposal + 0x11, 1) };
        if unsafe { byte(proposal + 0x11) } == 1 {
            ARMED_SESSION.store(session, Ordering::Release);
            return 0;
        }
    } else if ARMED_SESSION.load(Ordering::Acquire) == session {
        let local_team = session + application::LOCAL_TEAM;
        if unsafe { byte(local_team) } == 0 {
            unsafe { write_byte(local_team, 1) };
            if unsafe { byte(local_team) } == 1 {
                return 1;
            }
        }
    }
    0xff
}

pub fn install(base: usize, mode: Mode) {
    BASE.store(base, Ordering::Relaxed);
    EXPERIMENT.store(mode == Mode::ProposalExperiment, Ordering::Release);
    let callbacks: [unsafe extern "C" fn(&InlineCtx); application::SITE_COUNT] = [
        local,
        participant,
        ready,
        before,
        after,
        submit,
        receive,
        stored,
    ];
    for (i, offset) in application::SITES.into_iter().enumerate() {
        let address = base + offset;
        // Skyline's inline pool is near main; require exactly one B patch and
        // unchanged adjacent instructions. Abort if installation was different.
        let left = unsafe { word(address - 4) };
        let right = unsafe { word(address + 4) };
        unsafe {
            A64InlineHook(address as *const c_void, callbacks[i] as *const c_void);
        }
        let instruction = unsafe { word(address) };
        if instruction & 0xfc00_0000 != 0x1400_0000
            || unsafe { word(address - 4) } != left
            || unsafe { word(address + 4) } != right
        {
            std::process::abort();
        }
    }
}
pub fn start(tick: u64) {
    START.store(tick, Ordering::Relaxed);
    ACTIVE.store(true, Ordering::Release);
}
/// Stop only diagnostic event capture. The proposal experiment is process
/// scoped and intentionally remains enabled until Smash exits.
pub fn stop_recording() {
    ACTIVE.store(false, Ordering::Release);
}

unsafe fn observe(kind: usize, ctx: &InlineCtx) {
    let policy = application::hook_policy(
        EXPERIMENT.load(Ordering::Acquire),
        ACTIVE.load(Ordering::Acquire),
    );
    // Only local-copy and rule-submit hooks can mutate. Once recording ends,
    // all other callbacks return without reading game state.
    if !policy.record && (!policy.mutate || !matches!(kind, 0 | 5)) {
        return;
    }
    // At submit entry the original ABI is (session, u16 command, buffer,
    // u32 length, flags). Skip all other commands before touching memory.
    if kind == 5
        && (ctx.registers[1].x() as u16 != 0xb4
            || ctx.registers[3].x() as u32 != 0xd0
            || ctx.registers[2].x() == 0)
    {
        return;
    }
    let mutation_action = if policy.mutate && matches!(kind, 0 | 5) {
        unsafe { mutate_if_guarded(kind, ctx) }
    } else {
        0xff
    };
    if !policy.record {
        return;
    }
    CALLS[kind].fetch_add(1, Ordering::Relaxed);
    let base = BASE.load(Ordering::Relaxed);
    let mode = unsafe { word(base + application::MODE_OFFSET) };
    let bank = kind
        + if mode == application::COOP_MODE {
            application::SITE_COUNT
        } else {
            0
        };
    if !EVENTS[bank].try_capture(application::BANK_LIMIT, || {
        // Original code consumes these pointers on this synchronous path.
        // Never retain them or log full packets, player or profile data.
        let session = if kind == 5 {
            ctx.registers[0].x() as usize
        } else if kind >= 6 {
            ctx.registers[19].x() as usize - 0xa010
        } else {
            ctx.registers[24].x() as usize
        };
        let base = BASE.load(Ordering::Relaxed);
        let mut participant = 0xff;
        let team = if kind == 0 {
            unsafe { byte(session + application::LOCAL_TEAM) }
        } else if kind == 1 {
            let source = ctx.registers[1].x() as usize;
            match application::participant_slot(session, source) {
                Some(slot) => {
                    participant = slot;
                    unsafe { byte(source + 0xf11) }
                }
                None => 0xff,
            }
        } else if kind == 5 {
            let buffer = ctx.registers[2].x() as usize;
            let slot = unsafe { byte(buffer + 0xc8) };
            if slot < 16 {
                participant = slot;
            }
            unsafe { byte(buffer + 0x11) }
        } else if kind == 6 {
            // Original B4 size/index checks and C8 load have already run.
            let slot = ctx.registers[9].x();
            if slot < 16 {
                participant = slot as u8;
            }
            unsafe { byte(ctx.registers[8].x() as usize + 0x11) }
        } else if kind == 7 {
            let record = ctx.registers[9].x() as usize;
            match application::received_slot(ctx.registers[19].x() as usize, record) {
                Some(slot) => {
                    participant = slot;
                    unsafe { byte(record + 0x1699) }
                }
                None => 0xff,
            }
        } else {
            unsafe { byte(session + application::SELECTED_TEAM) }
        };
        let local_slot = unsafe { local_slot(session) };
        let selected_owner = if kind == 0 {
            local_slot
        } else if kind == 1 {
            participant
        } else {
            0xff
        };
        let submit_origin = if kind == 5 {
            application::submit_origin((ctx.registers[30].x() as usize).wrapping_sub(base))
        } else {
            0xff
        };
        let initialized = unsafe { byte(base + watch::GUARD_OFFSET) } & 1 != 0;
        Event {
            kind: kind as u8,
            prepared: unsafe { byte(session + application::SESSION_PREPARED) },
            team,
            global: if initialized {
                unsafe { byte(base + watch::GLOBAL_OFFSET) }
            } else {
                0xff
            },
            initialized,
            participant,
            local_slot,
            selected_owner,
            submit_origin,
            mutation_action,
            mode,
            request: unsafe { word(session + application::SESSION_REQUEST) },
            elapsed_ticks: unsafe { skyline::nn::os::GetSystemTick() }
                .wrapping_sub(START.load(Ordering::Relaxed)),
        }
        .encode()
    }) {
        DROPPED.fetch_add(1, Ordering::Relaxed);
    }
}
unsafe extern "C" fn local(c: &InlineCtx) {
    unsafe { observe(0, c) }
}
unsafe extern "C" fn participant(c: &InlineCtx) {
    unsafe { observe(1, c) }
}
unsafe extern "C" fn ready(c: &InlineCtx) {
    unsafe { observe(2, c) }
}
unsafe extern "C" fn before(c: &InlineCtx) {
    unsafe { observe(3, c) }
}
unsafe extern "C" fn after(c: &InlineCtx) {
    unsafe { observe(4, c) }
}
unsafe extern "C" fn submit(c: &InlineCtx) {
    unsafe { observe(5, c) }
}
unsafe extern "C" fn receive(c: &InlineCtx) {
    unsafe { observe(6, c) }
}
unsafe extern "C" fn stored(c: &InlineCtx) {
    unsafe { observe(7, c) }
}

pub fn counts() -> ([usize; application::SITE_COUNT], usize) {
    (
        std::array::from_fn(|i| CALLS[i].load(Ordering::Relaxed)),
        DROPPED.load(Ordering::Relaxed),
    )
}
pub fn drain(log: &mut CaptureLog) -> io::Result<bool> {
    let mut dirty = false;
    for (bank, store) in EVENTS.iter().enumerate() {
        for i in 0..application::BANK_LIMIT {
            if let Some(capture) = store.take(i) {
                log.event(
                    &Event::decode(&capture.bytes)
                        .line(bank * application::BANK_LIMIT + capture.sequence),
                )?;
                dirty = true;
            }
        }
    }
    Ok(dirty)
}
