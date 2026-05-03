use std::io::BufRead;
use std::process::{Command, Stdio};
use std::sync::mpsc;
use std::thread;
use std::time::{Duration, Instant};
use std::fs;

const STARTUP_TIMEOUT: u64 = 45;

fn ensure_no_blocking_files() {
    let pending = "agents/hire_requests/pending";
    let ask_user = "agents/_ask_user.json";
    if let Ok(entries) = fs::read_dir(pending) {
        for entry in entries.flatten() {
            let path = entry.path();
            if path.extension().and_then(|e| e.to_str()) == Some("json") {
                let _ = fs::remove_file(&path);
            }
        }
    }
    if fs::metadata(ask_user).is_ok() {
        let _ = fs::remove_file(ask_user);
    }
}

#[test]
fn test_e2e_core_startup_and_health_check() {
    ensure_no_blocking_files();

    // Build first
    let build_output = Command::new("cargo")
        .args(["build"])
        .output()
        .expect("failed to build");
    assert!(build_output.status.success(), "cargo build failed");

    // Run the binary
    let mut child = match Command::new("cargo")
        .args(["run", "--quiet"])
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(c) => c,
        Err(e) => panic!("failed to start cococat: {e}"),
    };

    let stdout = child.stdout.take().expect("no stdout");

    // Read stdout in a separate thread to avoid blocking
    let (tx, rx) = mpsc::channel::<String>();
    let handle = thread::spawn(move || {
        let reader = std::io::BufReader::new(stdout);
        for line in reader.lines() {
            match line {
                Ok(l) => {
                    if tx.send(l).is_err() {
                        break;
                    }
                }
                Err(_) => break,
            }
        }
    });

    let start = Instant::now();
    let mut found_startup = false;
    let mut found_config = false;
    let mut found_health = false;
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
                if line.contains("Health Check") {
                    found_health = true;
                }
                if line.contains("Team Roster") {
                    found_roster = true;
                }
                if found_startup && found_config && found_health && found_roster {
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
    assert!(found_health, "Missing: health check section");
    assert!(found_roster, "Missing: team roster section");
}
