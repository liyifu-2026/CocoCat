use std::io::{BufRead, BufReader, Write};
use std::process::{Command, Stdio};
use std::time::{Duration, Instant};

const TIMEOUT_SECS: u64 = 30;

#[test]
fn test_agent_runtime_ping_pong() {
    let mut child = Command::new("python3")
        .args(["-u", "py-agent/agent_runtime.py", "--id", "e2e_test", "--name", "E2E Test"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("failed to spawn agent_runtime.py");

    let stdin = child.stdin.as_mut().expect("no stdin");
    let stdout = child.stdout.take().expect("no stdout");
    let mut reader = BufReader::new(stdout);

    let request = r#"{"jsonrpc":"2.0","method":"ping","params":{},"id":1}"#;
    writeln!(stdin, "{}", request).expect("failed to write to stdin");
    stdin.flush().expect("failed to flush stdin");

    let start = Instant::now();
    let mut response = String::new();
    loop {
        if start.elapsed() > Duration::from_secs(TIMEOUT_SECS) {
            panic!("Timeout waiting for pong response");
        }
        response.clear();
        match reader.read_line(&mut response) {
            Ok(0) => panic!("EOF before response"),
            Ok(_) => break,
            Err(e) => {
                if e.kind() == std::io::ErrorKind::WouldBlock {
                    std::thread::sleep(Duration::from_millis(100));
                    continue;
                }
                panic!("read error: {e}");
            }
        }
    }

    let resp: serde_json::Value = serde_json::from_str(&response.trim())
        .expect("failed to parse response JSON");

    assert_eq!(resp["jsonrpc"], "2.0", "not JSON-RPC 2.0");
    assert!(resp["result"]["pong"].as_bool().unwrap_or(false), "expected pong=true");
    assert_eq!(resp["id"], 1, "id mismatch");

    let _ = child.kill();
    let _ = child.wait();
}

#[test]
fn test_agent_runtime_echo() {
    let mut child = Command::new("python3")
        .args(["-u", "py-agent/agent_runtime.py", "--id", "e2e_echo", "--name", "Echo Test"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("failed to spawn agent_runtime.py");

    let stdin = child.stdin.as_mut().expect("no stdin");
    let stdout = child.stdout.take().expect("no stdout");
    let mut reader = BufReader::new(stdout);

    let request = r#"{"jsonrpc":"2.0","method":"echo","params":{"hello":"world","value":42},"id":2}"#;
    writeln!(stdin, "{}", request).expect("failed to write to stdin");
    stdin.flush().expect("failed to flush stdin");

    let start = Instant::now();
    let mut response = String::new();
    loop {
        if start.elapsed() > Duration::from_secs(TIMEOUT_SECS) {
            panic!("Timeout waiting for echo response");
        }
        response.clear();
        match reader.read_line(&mut response) {
            Ok(0) => panic!("EOF before response"),
            Ok(_) => break,
            Err(e) => {
                if e.kind() == std::io::ErrorKind::WouldBlock {
                    std::thread::sleep(Duration::from_millis(100));
                    continue;
                }
                panic!("read error: {e}");
            }
        }
    }

    let resp: serde_json::Value = serde_json::from_str(&response.trim())
        .expect("failed to parse response JSON");
    assert_eq!(resp["result"]["hello"], "world");
    assert_eq!(resp["result"]["value"], 42);
    assert_eq!(resp["id"], 2);

    let _ = child.kill();
    let _ = child.wait();
}

#[test]
fn test_agent_runtime_identify() {
    let mut child = Command::new("python3")
        .args(["-u", "py-agent/agent_runtime.py", "--id", "e2e_id", "--name", "ID Test"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("failed to spawn agent_runtime.py");

    let stdin = child.stdin.as_mut().expect("no stdin");
    let stdout = child.stdout.take().expect("no stdout");
    let mut reader = BufReader::new(stdout);

    let request = r#"{"jsonrpc":"2.0","method":"identify","params":{},"id":3}"#;
    writeln!(stdin, "{}", request).expect("failed to write to stdin");
    stdin.flush().expect("failed to flush stdin");

    let start = Instant::now();
    let mut response = String::new();
    loop {
        if start.elapsed() > Duration::from_secs(TIMEOUT_SECS) {
            panic!("Timeout waiting for identify response");
        }
        response.clear();
        match reader.read_line(&mut response) {
            Ok(0) => panic!("EOF before response"),
            Ok(_) => break,
            Err(e) => {
                if e.kind() == std::io::ErrorKind::WouldBlock {
                    std::thread::sleep(Duration::from_millis(100));
                    continue;
                }
                panic!("read error: {e}");
            }
        }
    }

    let resp: serde_json::Value = serde_json::from_str(&response.trim())
        .expect("failed to parse response JSON");
    assert_eq!(resp["result"]["id"], "e2e_id");
    assert_eq!(resp["result"]["name"], "ID Test");

    let _ = child.kill();
    let _ = child.wait();
}

#[test]
fn test_agent_runtime_invalid_json() {
    let mut child = Command::new("python3")
        .args(["-u", "py-agent/agent_runtime.py", "--id", "e2e_bad", "--name", "Bad Test"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("failed to spawn agent_runtime.py");

    let stdin = child.stdin.as_mut().expect("no stdin");
    let stdout = child.stdout.take().expect("no stdout");
    let mut reader = BufReader::new(stdout);

    writeln!(stdin, "not valid json").expect("failed to write to stdin");
    stdin.flush().expect("failed to flush stdin");

    let start = Instant::now();
    let mut response = String::new();
    loop {
        if start.elapsed() > Duration::from_secs(TIMEOUT_SECS) {
            panic!("Timeout waiting for error response");
        }
        response.clear();
        match reader.read_line(&mut response) {
            Ok(0) => panic!("EOF before response"),
            Ok(_) => break,
            Err(e) => {
                if e.kind() == std::io::ErrorKind::WouldBlock {
                    std::thread::sleep(Duration::from_millis(100));
                    continue;
                }
                panic!("read error: {e}");
            }
        }
    }

    let resp: serde_json::Value = serde_json::from_str(&response.trim())
        .expect("failed to parse response JSON");
    assert_eq!(resp["jsonrpc"], "2.0");
    assert!(resp["error"]["code"].as_i64().unwrap_or(0) < 0, "expected error code");

    let _ = child.kill();
    let _ = child.wait();
}

#[test]
fn test_agent_runtime_multiple_requests() {
    let mut child = Command::new("python3")
        .args(["-u", "py-agent/agent_runtime.py", "--id", "e2e_multi", "--name", "Multi Test"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .expect("failed to spawn agent_runtime.py");

    let stdin = child.stdin.as_mut().expect("no stdin");
    let stdout = child.stdout.take().expect("no stdout");
    let mut reader = BufReader::new(stdout);

    for i in 0..3 {
        let request = format!(r#"{{"jsonrpc":"2.0","method":"echo","params":{{"seq":{}}},"id":{}}}"#, i, i + 10);
        writeln!(stdin, "{}", request).expect("failed to write to stdin");
        stdin.flush().expect("failed to flush stdin");

        let start = Instant::now();
        let mut response = String::new();
        loop {
            if start.elapsed() > Duration::from_secs(10) {
                panic!("Timeout waiting for response {i}");
            }
            response.clear();
            match reader.read_line(&mut response) {
                Ok(0) => panic!("EOF before response {i}"),
                Ok(_) => break,
                Err(e) => {
                    if e.kind() == std::io::ErrorKind::WouldBlock {
                        std::thread::sleep(Duration::from_millis(100));
                        continue;
                    }
                    panic!("read error: {e}");
                }
            }
        }

        let resp: serde_json::Value = serde_json::from_str(&response.trim())
            .expect("failed to parse response JSON");
        assert_eq!(resp["result"]["seq"], i, "seq mismatch for request {i}");
        assert_eq!(resp["id"], i + 10, "id mismatch for request {i}");
    }

    let _ = child.kill();
    let _ = child.wait();
}
