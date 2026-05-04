use std::io::{Read, Write};
use std::net::TcpStream;
use std::process::{Command, Stdio};
use std::time::Duration;

/// E2E test for Phase 1 core.
/// Starts the daemon with a temp database, sends a health check, then shuts down.
///
/// Run with:
///   cargo build --bin cococat && cargo test --test integration_test -- --nocache --ignored
#[tokio::test]
#[ignore]
async fn test_daemon_health_check() {
    let tmp_dir = std::env::temp_dir().join(format!("cococat_e2e_{:x}", rand_u64()));
    std::fs::create_dir_all(&tmp_dir).unwrap();

    let db_path = tmp_dir.join("test.db");

    // Seed a test agent
    let conn = rusqlite::Connection::open(&db_path).unwrap();
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            model TEXT NOT NULL,
            scene_id TEXT NOT NULL DEFAULT 'default',
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

    let bin_path = std::env::current_dir().unwrap().join("target/debug/cococat");
    let mut child = Command::new(&bin_path)
        .env("COCOCAT_DB", db_path.to_str().unwrap())
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .expect("Failed to start cococat daemon. Build first with: cargo build --bin cococat");

    // Wait for startup
    std::thread::sleep(Duration::from_secs(3));

    // Check health via raw TCP
    let result = (|| -> Result<String, String> {
        let mut stream = TcpStream::connect("127.0.0.1:3000")
            .map_err(|e| format!("connect: {}", e))?;
        let request = "GET /api/health HTTP/1.0\r\n\r\n";
        stream.write_all(request.as_bytes())
            .map_err(|e| format!("write: {}", e))?;
        let mut buf = String::new();
        stream.read_to_string(&mut buf)
            .map_err(|e| format!("read: {}", e))?;
        Ok(buf)
    })();

    // Cleanup daemon
    let _ = child.kill();
    let _ = child.wait();
    let _ = std::fs::remove_dir_all(&tmp_dir);

    // Check result
    let response = result.unwrap_or_else(|e| panic!("Health check failed: {}", e));
    assert!(
        response.contains("200 OK") || response.contains("200 ok"),
        "Expected 200 OK, got: {}",
        response
    );
}

fn rand_u64() -> u64 {
    use std::time::{SystemTime, UNIX_EPOCH};
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_nanos();
    (nanos ^ (nanos >> 32)) as u64
}
