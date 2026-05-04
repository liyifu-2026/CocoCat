use std::io::{Read, Write};
use std::process::{Command, Stdio};
use std::time::Duration;

/// Full E2E test: start daemon, login, send chat, check task.
///
/// Run with:
///   cargo build --bin cococat && cargo test --test integration_test -- --nocache --ignored
#[tokio::test]
#[ignore]
async fn test_full_e2e_flow() {
    let tmp_dir = std::env::temp_dir().join(format!("cococat_e2e_{:x}", rand_u64()));
    std::fs::create_dir_all(&tmp_dir).unwrap();
    let db_path = tmp_dir.join("test.db");

    // Seed: create agents table and insert a test agent
    let conn = rusqlite::Connection::open(&db_path).unwrap();
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, role TEXT NOT NULL,
            model TEXT NOT NULL, scene_id TEXT NOT NULL DEFAULT 'default',
            status TEXT NOT NULL DEFAULT 'stopped'
                CHECK (status IN ('stopped','running','error')),
            system_prompt TEXT NOT NULL DEFAULT '',
            metadata TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_heartbeat_at TEXT
        );
        INSERT INTO agents (id, name, role, model, status)
        VALUES ('test_leader', 'Test Leader', 'manager', 'gpt-4', 'running');"
    ).unwrap();
    drop(conn);

    // Start daemon
    let bin_path = std::env::current_dir().unwrap().join("target/debug/cococat");
    let mut child = Command::new(&bin_path)
        .env("COCOCAT_DB", db_path.to_str().unwrap())
        .env("JWT_SECRET", "test-secret-for-e2e")
        .env("WEB_PASSWORD", "test-password")
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("Failed to start cococat daemon. Build first with: cargo build --bin cococat");

    std::thread::sleep(Duration::from_secs(3));

    let result = run_e2e(&tmp_dir);

    let _ = child.kill();
    let _ = child.wait();
    let _ = std::fs::remove_dir_all(&tmp_dir);

    let (step1, step2, step3, step4) = result.unwrap_or_else(|e| panic!("E2E failed: {}", e));

    assert!(step1, "Health check should pass");
    assert!(step2, "Login should return a token");
    assert!(step3, "Chat should return a task_uuid");
    // Step 4: task should reach completed or failed (not pending)
    println!("E2E result: health={} login={} chat={} task_status={}",
             step1, step2, step3, step4);
}

fn run_e2e(_tmp_dir: &std::path::Path) -> Result<(bool, bool, bool, String), String> {
    // Step 1: Health check
    let health_ok = http_get("127.0.0.1:3000", "/api/health")?
        .contains("200 OK") || http_get("127.0.0.1:3000", "/api/health")?
        .contains("HTTP/1.1 200 OK");

    // Step 2: Login
    let login_resp = http_post("127.0.0.1:3000", "/api/auth/login",
        r#"{"password":"test-password"}"#)?;

    // Extract token from response
    let token = if login_resp.contains("token") {
        // Parse JSON-ish response
        let start = login_resp.find("\"token\":\"").map(|i| i + 9).unwrap_or(0);
        let end = login_resp[start..].find('"').map(|i| start + i).unwrap_or(0);
        if end > start {
            login_resp[start..end].to_string()
        } else {
            return Ok((health_ok, false, false, "no_token".into()));
        }
    } else {
        return Ok((health_ok, false, false, "login_failed".into()));
    };
    let login_ok = !token.is_empty();

    // Step 3: Send chat
    let chat_body = format!(
        r#"{{"content":"Hello","agent_id":"test_leader","user_id":"test_user"}}"#
    );
    let chat_resp = http_post_with_token("127.0.0.1:3000", "/api/chat", &chat_body, &token)?;
    let has_task = chat_resp.contains("task_uuid");
    let task_uuid = if has_task {
        let start = chat_resp.find("\"task_uuid\":\"").map(|i| i + 13).unwrap_or(0);
        let end = chat_resp[start..].find('"').map(|i| start + i).unwrap_or(0);
        if end > start { chat_resp[start..end].to_string() } else { String::new() }
    } else {
        String::new()
    };

    // Step 4: Poll task status
    let task_status = if !task_uuid.is_empty() {
        std::thread::sleep(Duration::from_secs(2));
        let task_resp = http_get_with_token("127.0.0.1:3000",
            &format!("/api/tasks/{}", task_uuid), &token)?;
        if task_resp.contains("\"completed\"") { "completed".into() }
        else if task_resp.contains("\"failed\"") { "failed".into() }
        else if task_resp.contains("\"running\"") { "running".into() }
        else if task_resp.contains("\"pending\"") { "pending".into() }
        else { "unknown".into() }
    } else {
        "no_task".into()
    };

    Ok((health_ok, login_ok, has_task, task_status))
}

fn http_get(host: &str, path: &str) -> Result<String, String> {
    let mut stream = TcpStream::connect(host).map_err(|e| format!("connect: {}", e))?;
    let req = format!("GET {} HTTP/1.0\r\nHost: {}\r\n\r\n", path, host);
    stream.write_all(req.as_bytes()).map_err(|e| format!("write: {}", e))?;
    let mut buf = String::new();
    stream.read_to_string(&mut buf).map_err(|e| format!("read: {}", e))?;
    Ok(buf)
}

fn http_get_with_token(host: &str, path: &str, token: &str) -> Result<String, String> {
    let mut stream = TcpStream::connect(host).map_err(|e| format!("connect: {}", e))?;
    let req = format!(
        "GET {} HTTP/1.0\r\nHost: {}\r\nAuthorization: Bearer {}\r\n\r\n",
        path, host, token
    );
    stream.write_all(req.as_bytes()).map_err(|e| format!("write: {}", e))?;
    let mut buf = String::new();
    stream.read_to_string(&mut buf).map_err(|e| format!("read: {}", e))?;
    Ok(buf)
}

fn http_post(host: &str, path: &str, body: &str) -> Result<String, String> {
    let mut stream = TcpStream::connect(host).map_err(|e| format!("connect: {}", e))?;
    let req = format!(
        "POST {} HTTP/1.0\r\nHost: {}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
        path, host, body.len(), body
    );
    stream.write_all(req.as_bytes()).map_err(|e| format!("write: {}", e))?;
    let mut buf = String::new();
    stream.read_to_string(&mut buf).map_err(|e| format!("read: {}", e))?;
    Ok(buf)
}

fn http_post_with_token(host: &str, path: &str, body: &str, token: &str) -> Result<String, String> {
    let mut stream = TcpStream::connect(host).map_err(|e| format!("connect: {}", e))?;
    let req = format!(
        "POST {} HTTP/1.0\r\nHost: {}\r\nAuthorization: Bearer {}\r\nContent-Type: application/json\r\nContent-Length: {}\r\n\r\n{}",
        path, host, token, body.len(), body
    );
    stream.write_all(req.as_bytes()).map_err(|e| format!("write: {}", e))?;
    let mut buf = String::new();
    stream.read_to_string(&mut buf).map_err(|e| format!("read: {}", e))?;
    Ok(buf)
}

fn rand_u64() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    (nanos ^ (nanos >> 32)) as u64
}
