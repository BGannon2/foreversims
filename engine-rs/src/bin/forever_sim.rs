//! Command-line runner for parity checks against the Python reference.
//!
//!   forever-sim spec    request.json  [--data ../web/data]
//!   forever-sim paladin profile.json  [--data ../web/data]
//!
//! Prints the result JSON (or {"error": ...}) to stdout.

use std::fs;
use std::path::PathBuf;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    if args.len() < 3 {
        eprintln!("usage: forever-sim <spec|paladin> <request.json> [--data <web/data dir>]");
        std::process::exit(2);
    }
    let kind = args[1].as_str();
    let input = fs::read_to_string(&args[2]).expect("read request");
    let mut data_dir = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("web").join("data");
    if let Some(i) = args.iter().position(|a| a == "--data") {
        data_dir = PathBuf::from(&args[i + 1]);
    }
    let read = |name: &str| fs::read_to_string(data_dir.join(name)).unwrap_or_else(|e| panic!("{name}: {e}"));
    let catalog = forever_engine::items::load_catalog(&read("items.json"), &read("engine-items-extra.json"), &read("enchants.json"), &read("forever-sets.json")).expect("catalog");
    forever_engine::set_catalog_native(catalog);
    let output = match kind {
        "spec" => forever_engine::simulate_spec(&input),
        "paladin" => forever_engine::simulate_paladin(&input),
        _ => {
            eprintln!("kind must be spec or paladin");
            std::process::exit(2);
        }
    };
    println!("{output}");
}
