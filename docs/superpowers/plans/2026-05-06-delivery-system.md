# Delivery System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** Add one-way deliverable inbox where agents send completed work to admin.

**Architecture:** New `deliveries` SQLite table, Python tool for agents, Rust API endpoints, FastAPI proxy, frontend rewrite.

**Tech Stack:** Rust (rusqlite, axum), Python (tool), FastAPI (httpx), React/TypeScript

---

### Task 1: Rust — deliveries table + DB module + API

**Files:**
- Modify: `src/db/pool.rs` — add CREATE TABLE
- Create: `src/db/deliveries.rs` — DB operations
- Create: `src/api/deliveries.rs` — REST handlers
- Modify: `src/db/mod.rs` — register module
- Modify: `src/api/mod.rs` — register module
- Modify: `src/api/router.rs` — add routes
- Modify: `src/main.rs` — add file serving

- [ ] **Step 1: Add table to pool.rs**

```sql
        CREATE TABLE IF NOT EXISTS deliveries (
            id TEXT PRIMARY KEY,
            subject TEXT NOT NULL,
            from_agent TEXT NOT NULL,
            body TEXT NOT NULL DEFAULT '',
            files TEXT NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
```

- [ ] **Step 2: Create src/db/deliveries.rs**

```rust
use crate::db::pool::DbPool;
use rusqlite::params;
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DeliveryFile {
    pub name: String,
    pub path: String,
    pub size: i64,
    pub mime: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Delivery {
    pub id: String,
    pub subject: String,
    pub from_agent: String,
    pub body: String,
    pub files: Vec<DeliveryFile>,
    pub status: String,
    pub created_at: String,
}

pub fn create_delivery(
    pool: &DbPool,
    id: &str,
    subject: &str,
    from_agent: &str,
    body: &str,
    files_json: &str,
) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute(
        "INSERT INTO deliveries (id, subject, from_agent, body, files) VALUES (?1, ?2, ?3, ?4, ?5)",
        params![id, subject, from_agent, body, files_json],
    )?;
    Ok(())
}

pub fn list_deliveries(pool: &DbPool) -> Result<Vec<Delivery>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, subject, from_agent, body, files, status, created_at FROM deliveries ORDER BY created_at DESC"
    )?;
    let deliveries = stmt.query_map([], |row| {
        let files_str: String = row.get(4)?;
        let files: Vec<DeliveryFile> = serde_json::from_str(&files_str).unwrap_or_default();
        Ok(Delivery {
            id: row.get(0)?,
            subject: row.get(1)?,
            from_agent: row.get(2)?,
            body: row.get(3)?,
            files,
            status: row.get(5)?,
            created_at: row.get(6)?,
        })
    })?
    .filter_map(|r| r.ok())
    .collect();
    Ok(deliveries)
}

pub fn get_delivery(pool: &DbPool, id: &str) -> Result<Option<Delivery>, Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    let mut stmt = conn.prepare(
        "SELECT id, subject, from_agent, body, files, status, created_at FROM deliveries WHERE id = ?1"
    )?;
    let mut rows = stmt.query_map(params![id], |row| {
        let files_str: String = row.get(4)?;
        let files: Vec<DeliveryFile> = serde_json::from_str(&files_str).unwrap_or_default();
        Ok(Delivery {
            id: row.get(0)?,
            subject: row.get(1)?,
            from_agent: row.get(2)?,
            body: row.get(3)?,
            files,
            status: row.get(5)?,
            created_at: row.get(6)?,
        })
    })?;
    Ok(rows.next().and_then(|r| r.ok()))
}

pub fn update_status(pool: &DbPool, id: &str, status: &str) -> Result<(), Box<dyn std::error::Error>> {
    let conn = pool.get()?;
    conn.execute("UPDATE deliveries SET status = ?1 WHERE id = ?2", params![status, id])?;
    Ok(())
}
```

- [ ] **Step 3: Create src/api/deliveries.rs**

```rust
use axum::{
    extract::{Path, State},
    http::{HeaderMap, StatusCode, header},
    response::IntoResponse,
    Json,
};
use crate::auth;
use crate::db::deliveries as db_del;
use super::router::AppState;
use std::path::PathBuf;

pub async fn list_deliveries(
    State(state): State<AppState>,
    headers: HeaderMap,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let deliveries = db_del::list_deliveries(&state.db_pool)
        .map_err(|e| { tracing::error!("list_deliveries: {}", e); StatusCode::INTERNAL_SERVER_ERROR })?;
    Ok(Json(serde_json::json!({"deliveries": deliveries})))
}

pub async fn get_delivery(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    match db_del::get_delivery(&state.db_pool, &id)
        .map_err(|e| { tracing::error!("get_delivery: {}", e); StatusCode::INTERNAL_SERVER_ERROR })? {
        Some(d) => Ok(Json(serde_json::to_value(d).unwrap())),
        None => Ok(Json(serde_json::json!({"error": "not found"}))),
    }
}

pub async fn archive_delivery(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_del::update_status(&state.db_pool, &id, "archived")
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(serde_json::json!({"status": "archived"})))
}

pub async fn mark_read(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path(id): Path<String>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    db_del::update_status(&state.db_pool, &id, "read")
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(serde_json::json!({"status": "read"})))
}

pub async fn download_file(
    State(state): State<AppState>,
    headers: HeaderMap,
    Path((id, filename)): Path<(String, String)>,
) -> Result<axum::response::Response, StatusCode> {
    auth::verify_token(&headers, &state.jwt)?;
    let base = PathBuf::from("data/deliveries").join(&id);
    let file_path = base.join(&filename);
    if !file_path.exists() {
        return Ok(Json(serde_json::json!({"error": "file not found"})).into_response());
    }
    let data = tokio::fs::read(&file_path).await
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    let mime = mime_guess::from_path(&filename).first_or_octet_stream();
    Ok(([(header::CONTENT_TYPE, mime.as_ref())], data).into_response())
}
```

- [ ] **Step 4: Register module + routes**

src/db/mod.rs: `pub mod deliveries;`
src/api/mod.rs: `pub mod deliveries;`

src/api/router.rs: add `use super::deliveries;` and routes:
```rust
        .route("/api/deliveries", axum::routing::get(deliveries::list_deliveries))
        .route("/api/deliveries/:id", axum::routing::get(deliveries::get_delivery))
        .route("/api/deliveries/:id/archive", axum::routing::post(deliveries::archive_delivery))
        .route("/api/deliveries/:id/read", axum::routing::post(deliveries::mark_read))
        .route("/api/deliveries/:id/files/:filename", axum::routing::get(deliveries::download_file))
```

Add `mime_guess = "2"` to Cargo.toml dependencies.

- [ ] **Step 5: Verify compilation**

Run: `cargo check --bin cococat`

- [ ] **Step 6: Commit**

```bash
git add src/ Cargo.toml Cargo.lock
git commit -m "feat: add deliveries table, DB module, and API endpoints"
```

---

### Task 2: Python — send_delivery tool

**Files:**
- Create: `py-agent/skills/send_delivery.py`
- Modify: `py-agent/tools.py` — register tool

- [ ] **Step 1: Create the tool**

```python
"""Tool: Send a delivery to admin's mailbox with files."""
import json, os, shutil, uuid, datetime

TOOL_DEF = {
    "type": "function",
    "function": {
        "name": "send_delivery",
        "description": "完成任务后将成果交付给管理员。将文件发送到管理员的交付收件箱。",
        "parameters": {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "交付主题"},
                "body": {"type": "string", "description": "交付说明"},
                "file_paths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "需要交付的文件路径列表",
                },
            },
            "required": ["subject"],
        },
    },
}

def send_delivery(subject: str, body: str = "", file_paths: list | None = None, **kwargs) -> str:
    import httpx
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    delivery_id = str(uuid.uuid4())[:8]
    dest_dir = os.path.join(base_dir, "data", "deliveries", delivery_id)
    os.makedirs(dest_dir, exist_ok=True)
    
    files_meta = []
    for fp in (file_paths or []):
        src = os.path.abspath(fp)
        if not os.path.exists(src):
            continue
        name = os.path.basename(src)
        size = os.path.getsize(src)
        shutil.copy2(src, os.path.join(dest_dir, name))
        files_meta.append({"name": name, "path": f"data/deliveries/{delivery_id}/{name}", "size": size, "mime": "application/octet-stream"})
    
    # Write to Rust core API
    try:
        resp = httpx.post(
            f"http://localhost:3000/api/deliveries/create",
            json={
                "id": delivery_id,
                "subject": subject,
                "from_agent": kwargs.get("agent_id", "agent"),
                "body": body,
                "files_json": json.dumps(files_meta),
            },
            timeout=5,
        )
        resp.raise_for_status()
    except Exception as e:
        return f"交付记录写入失败: {e}"
    
    file_count = len(files_meta)
    return f"✅ 已交付「{subject}」到管理员邮箱，{'包含 '+str(file_count)+' 个附件' if file_count else '无附件'}。"

def run(**kwargs) -> str:
    return send_delivery(**kwargs)
```

- [ ] **Step 2: Register in tools.py**

In `create_default_registry()`, add:
```python
    try:
        from skills.send_delivery import send_delivery, TOOL_DEF as DELIVERY_DEF
        registry.add_dynamic_tool("send_delivery", send_delivery, DELIVERY_DEF)
    except ImportError:
        pass
```

- [ ] **Step 3: Add Rust create endpoint**

Need to add a create endpoint in the Rust API (for the tool to call). Add to `src/api/deliveries.rs`:

```rust
#[derive(Deserialize)]
pub struct CreateDeliveryRequest {
    pub id: String,
    pub subject: String,
    pub from_agent: String,
    pub body: String,
    pub files_json: String,
}

pub async fn create_delivery(
    State(state): State<AppState>,
    Json(req): Json<CreateDeliveryRequest>,
) -> Result<Json<serde_json::Value>, StatusCode> {
    // No auth required — called by internal tool
    db_del::create_delivery(&state.db_pool, &req.id, &req.subject, &req.from_agent, &req.body, &req.files_json)
        .map_err(|_| StatusCode::INTERNAL_SERVER_ERROR)?;
    Ok(Json(serde_json::json!({"status": "created"})))
}
```

Add route: `.route("/api/deliveries/create", axum::routing::post(deliveries::create_delivery))`

- [ ] **Step 4: Verify**

```bash
python3 -c "from skills.send_delivery import send_delivery; print('OK')"
cargo check --bin cococat
```

- [ ] **Step 5: Commit**

```bash
git add py-agent/skills/send_delivery.py py-agent/tools.py src/api/deliveries.rs src/api/router.rs
git commit -m "feat: add send_delivery tool for agent deliverables"
```

---

### Task 3: FastAPI proxy + Frontend rewrite

- [ ] **FastAPI proxy in web/main.py**

```python
@app.get("/api/deliveries")
async def list_deliveries(request: Request):
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth: headers["Authorization"] = auth
            resp = await client.get("http://localhost:3000/api/deliveries", headers=headers, timeout=10)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
        except httpx.RequestError as e:
            return JSONResponse({"error": f"Rust core unavailable: {e}"}, status_code=503)

@app.get("/api/deliveries/{delivery_id}")
async def get_delivery(request: Request, delivery_id: str):
    ... same pattern ...

@app.post("/api/deliveries/{delivery_id}/archive")
async def archive_delivery(request: Request, delivery_id: str):
    ... same pattern ...

@app.post("/api/deliveries/{delivery_id}/read")
async def mark_delivery_read(request: Request, delivery_id: str):
    ... same pattern ...

@app.get("/api/deliveries/{delivery_id}/files/{filename}")
async def download_delivery_file(request: Request, delivery_id: str, filename: str):
    # Proxy file download — pass through bytes
    import httpx
    async with httpx.AsyncClient() as client:
        try:
            headers = {}
            auth = request.headers.get("Authorization", "")
            if auth: headers["Authorization"] = auth
            resp = await client.get(f"http://localhost:3000/api/deliveries/{delivery_id}/files/{filename}", headers=headers)
            return Response(content=resp.content, media_type=resp.headers.get("content-type", "application/octet-stream"))
        except httpx.RequestError as e:
            return JSONResponse({"error": str(e)}, status_code=502)
```

- [ ] **Frontend: Rewrite Mailbox.tsx**

Replace the chat-like mailbox with a delivery inbox:
- Two-panel layout: left list + right detail
- List: rows with icon, subject, from_agent, time, status badge (new/read/archived)
- Detail: subject, from, body text, file list with download buttons
- Action buttons: Mark Read, Archive (no compose, no reply)
- Click file to download via `/api/deliveries/{id}/files/{name}`

- [ ] **Build and verify**

```bash
cd /home/leaif/CocoCat && cargo build --bin cococat
cd web-ui && npx tsc --noEmit && npm run build
```

- [ ] **Final commit**

```bash
git add -A
git commit -m "feat: complete delivery system"
```
