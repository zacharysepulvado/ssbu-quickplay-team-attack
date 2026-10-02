//! Local graphics only: no network message or shared rule UI is changed.
use crate::marker_state::{self, Status};
use imgui_api::bindings::*;

// The static client imports the host plugin's registered exports. The
// matching libimgui_smash.nro v1.0.0 must be installed beside this NRO.
#[link(name = "imgui_smash")]
unsafe extern "C" {}

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

unsafe extern "C" fn setup_context(context: *mut u64) {
    unsafe { igSetCurrentContext(context.cast()) };
}

unsafe extern "C" fn draw() {
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

pub fn install() {
    imgui_api::imgui_setup_context(setup_context);
    imgui_api::imgui_smash_add_on_draw_frame(draw as _);
}
