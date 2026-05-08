use std::path::PathBuf;

pub fn get_usage_log_path() -> PathBuf {
    if let Ok(workspace) = std::env::var("COCOCAT_WORKSPACE") {
        if !workspace.is_empty() {
            let mut p = PathBuf::from(workspace);
            p.push("agents");
            p.push("_usage.jsonl");
            return p;
        }
    }
    let mut p = PathBuf::from(env!("CARGO_MANIFEST_DIR"));
    p.push("agents");
    p.push("_usage.jsonl");
    p
}

pub fn read_usage(limit: usize) -> Vec<serde_json::Value> {
    let path = get_usage_log_path();
    if !path.exists() {
        return vec![];
    }
    let content = match std::fs::read_to_string(&path) {
        Ok(c) => c,
        Err(_) => return vec![],
    };
    let mut entries: Vec<serde_json::Value> = content
        .lines()
        .filter_map(|line| serde_json::from_str(line).ok())
        .collect();
    entries.reverse();
    entries.truncate(limit);
    entries
}
