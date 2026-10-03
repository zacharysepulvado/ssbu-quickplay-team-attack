//! Local graphics only: no network message or shared rule UI is changed.
use crate::marker_state::{self, Status};
use core::sync::atomic::{AtomicUsize, Ordering};
use imgui_api::bindings::*;
use skyline::libc::c_void;

// The renderer's C implementation is linked locally. Resolve its two host
// functions at runtime: a missing host must not prevent Smash
// from loading the Team Attack plugin or running the guarded proposal.
#[link(name = "imgui_smash")]
unsafe extern "C" {}

const GET_CONTEXT_SYMBOL: &[u8] = b"imgui_get_context_export\0";
const DRAW_FRAME_SYMBOL: &[u8] = b"imgui_smash_add_on_draw_frame_wrapper\0";
static GET_CONTEXT: AtomicUsize = AtomicUsize::new(0);

fn lookup(symbol: &'static [u8]) -> Option<usize> {
    let mut address = 0usize;
    let result = unsafe { skyline::nn::ro::LookupSymbol(&mut address, symbol.as_ptr()) };
    (result == 0 && address != 0).then_some(address)
}

const TITLE: &[u8] = b"##team_attack_selected\0";
const LABEL_ON: &[u8] = b"TEAM ATTACK: ON (selected)\0";
const LABEL_OFF: &[u8] = b"TEAM ATTACK: OFF (selected)\0";
const WINDOW_FLAGS: i32 = (ImGuiWindowFlags_NoInputs
    | ImGuiWindowFlags_NoNav
    | ImGuiWindowFlags_NoDecoration
    | ImGuiWindowFlags_NoSavedSettings
    | ImGuiWindowFlags_AlwaysAutoResize
    | ImGuiWindowFlags_NoFocusOnAppearing
    | ImGuiWindowFlags_NoBringToFrontOnFocus) as i32;

unsafe extern "C" fn draw() {
    // Query on the render thread, so registration works both before and after
    // the host creates its context. Never draw through a null/stale context.
    let address = GET_CONTEXT.load(Ordering::Acquire);
    if address == 0 {
        return;
    }
    let get_context: unsafe extern "C" fn() -> *mut u64 = unsafe { core::mem::transmute(address) };
    let context = unsafe { get_context() };
    if context.is_null() {
        return;
    }
    unsafe { igSetCurrentContext(context.cast()) };
    let now = unsafe { skyline::nn::os::GetSystemTick() };
    let (label, color) = match marker_state::current_recent(now, 90 * 19_200_000) {
        Status::On => (
            LABEL_ON,
            ImVec4 {
                x: 0.35,
                y: 0.95,
                z: 0.45,
                w: 1.0,
            },
        ),
        Status::Off => (
            LABEL_OFF,
            ImVec4 {
                x: 1.0,
                y: 0.45,
                z: 0.4,
                w: 1.0,
            },
        ),
        Status::Unknown => return,
    };
    unsafe {
        igSetNextWindowPos(
            ImVec2 { x: 24.0, y: 36.0 },
            ImGuiCond_Always as i32,
            ImVec2 { x: 0.0, y: 0.0 },
        );
        igSetNextWindowBgAlpha(0.75);
        if igBegin(TITLE.as_ptr().cast(), core::ptr::null_mut(), WINDOW_FLAGS) {
            igTextColored(color, label.as_ptr().cast());
        }
        igEnd();
    }
}

pub fn install() -> bool {
    let (Some(get_context), Some(add_draw)) =
        (lookup(GET_CONTEXT_SYMBOL), lookup(DRAW_FRAME_SYMBOL))
    else {
        skyline::println!("[team-attack] marker host unavailable; rule proposal remains active\n");
        return false;
    };
    // LookupSymbol returns these exact exported C signatures from the matching
    // imgui-smash host. Registration is skipped unless both exports exist.
    let add_draw: unsafe extern "C" fn(*const c_void) = unsafe { core::mem::transmute(add_draw) };
    GET_CONTEXT.store(get_context, Ordering::Release);
    unsafe {
        add_draw(draw as *const () as *const c_void);
    }
    skyline::println!("[team-attack] local marker render callback registered\n");
    true
}
