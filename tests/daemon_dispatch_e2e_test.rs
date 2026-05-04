use std::io::BufRead;
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};
use std::fs;

const STARTUP_TIMEOUT: u64 = 45;
const DISPATCH_TIMEOUT: u64 = 30;

fn ensure_clean_state() {
    let _ = fs::remove_dir_all("agents/dispatch_queue");
    fs::create_dir_all("agents/dispatch_queue").ok();
    let _ = fs::remove_dir_all("agents/dispatch_messages");
    fs::create_dir_all("agents/dispatch_messages").ok();
}

#[test]
fn test_daemon_startup_output() {
    ensure_clean_state();

    let build = Command::new("cargo")
        .args(["build", "--quiet"])
        .output()
        .expect("failed to build");
    assert!(build.status.success(), "cargo build failed");

    let mut child = Command::new("cargo")
        .args(["run", "--quiet"])
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("failed to start cococat");

    let stdout = child.stdout.take().expect("no stdout");
    let (tx, rx) = mpsc::channel::<String>();
    let handle = thread::spawn(move || {
        let reader = std::io::BufReader::new(stdout);
        for line in reader.lines() {
            if let Ok(l) = line {
                if tx.send(l).is_err() {
                    break;
                }
            }
        }
    });

    let start = Instant::now();
    let mut found_startup = false;
    let mut found_config = false;
    let mut found_roster = false;

    while start.elapsed() < Duration::from_secs(STARTUP_TIMEOUT) {
        match rx.recv_timeout(Duration::from_millis(200)) {
            Ok(line) => {
                if line.contains("CocoCat Core starting") {
                    found_startup = true;
                }
                if line.contains("Loaded") && line.contains("agent definitions") {
                    found_config = true;
                }
                if line.contains("Team Roster") {
                    found_roster = true;
                }
                if found_startup && found_config && found_roster {
                    break;
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => continue,
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }

    let _ = child.kill();
    let _ = child.wait();
    let _ = handle.join();

    assert!(found_startup, "Missing: CocoCat Core starting...");
    assert!(found_config, "Missing: agent config load");
    assert!(found_roster, "Missing: team roster section");
}

#[test]
fn test_daemon_removes_dispatch_file() {
    ensure_clean_state();

    let build = Command::new("cargo")
        .args(["build", "--quiet"])
        .output()
        .expect("failed to build");
    assert!(build.status.success(), "cargo build failed");

    let mut child = Command::new("cargo")
        .args(["run", "--quiet"])
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("failed to start cococat");

    let stdout = child.stdout.take().expect("no stdout");
    let (tx, rx) = mpsc::channel::<String>();
    let handle = thread::spawn(move || {
        let reader = std::io::BufReader::new(stdout);
        for line in reader.lines() {
            if let Ok(l) = line {
                if tx.send(l).is_err() {
                    break;
                }
            }
        }
    });

    let start = Instant::now();
    let mut daemon_ready = false;
    while start.elapsed() < Duration::from_secs(STARTUP_TIMEOUT) {
        match rx.recv_timeout(Duration::from_millis(200)) {
            Ok(line) => {
                if line.contains("Daemon Mode") {
                    daemon_ready = true;
                    break;
                }
            }
            Err(mpsc::RecvTimeoutError::Timeout) => continue,
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }
    assert!(daemon_ready, "Daemon did not start in time");

    let dispatch = serde_json::json!({
        "target_id": "leader",
        "method": "task",
        "params": {
            "prompt": "test dispatch"
        }
    });
    let dispatch_path = "agents/dispatch_queue/e2e_test_dispatch.json";
    fs::write(dispatch_path, serde_json::to_string_pretty(&dispatch).unwrap())
        .expect("failed to write dispatch file");

    let dispatch_start = Instant::now();
    let mut file_removed = false;
    while dispatch_start.elapsed() < Duration::from_secs(DISPATCH_TIMEOUT) {
        if !std::path::Path::new(dispatch_path).exists() {
            file_removed = true;
            break;
        }
        match rx.recv_timeout(Duration::from_millis(500)) {
            Ok(_) => continue,
            Err(mpsc::RecvTimeoutError::Timeout) => continue,
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }

    let _ = child.kill();
    let _ = child.wait();
    let _ = handle.join();

    assert!(file_removed, "Dispatch file was not removed by daemon within timeout");
}
