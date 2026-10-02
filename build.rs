fn main() {
    if std::env::var("CARGO_CFG_TARGET_OS").as_deref() == Ok("switch") {
        println!("cargo:rerun-if-changed=lib/libimgui_smash.a");
        println!("cargo:rustc-link-search=native=lib");
    }
}
