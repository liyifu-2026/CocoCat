# edit_file + ask_user Implementation Plan

**Goal:** Add `edit_file` (search/replace pattern matching) and `ask_user` (prompt user for input) tools.

---

### Task 1: Add edit_file tool

**Files:**
- Modify: `py-agent/tools.py`

- [ ] **Step 1: Add EditFileTool**

After `WebSearchTool`:

```python
class EditFileTool(Tool):
    """Replace text in a file using search/replace (claw-code pattern)."""
    name = "edit_file"
    description = "Replace text in a file. Specify old_string to find and new_string to replace it with. Use replace_all=true to replace all occurrences."
    parameters = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "description": "File path"},
            "old_string": {"type": "string", "description": "Text to find (exact match, not regex)"},
            "new_string": {"type": "string", "description": "Text to replace with"},
            "replace_all": {"type": "boolean", "description": "Replace all occurrences (default false)"},
        },
        "required": ["path", "old_string", "new_string"],
    }

    def execute(self, path="", old_string="", new_string="", replace_all=False, **kwargs) -> str:
        import os
        path = os.path.abspath(path)
        try:
            with open(path, "r", encoding="utf-8") as f:
                original = f.read()
        except FileNotFoundError:
            return f"Error: file not found: {path}"
        except Exception as e:
            return f"Error reading file: {e}"

        if old_string == new_string:
            return "Error: old_string and new_string must differ"

        if old_string not in original:
            return f"Error: old_string not found in file"

        if replace_all:
            updated = original.replace(old_string, new_string)
        else:
            updated = original.replace(old_string, new_string, 1)

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(updated)
        except Exception as e:
            return f"Error writing file: {e}"

        count = updated.count(new_string) - original.count(new_string)
        return f"Applied edit to {path}: replaced 1 occurrence" if not replace_all else f"Applied edit to {path}: replaced all occurrences"
```

- [ ] **Step 2: Register in create_default_registry**

```python
    registry.register(EditFileTool())
```

- [ ] **Step 3: Build and test**

```powershell
python -c "import sys; sys.path.insert(0,'py-agent'); from tools import EditFileTool; t = EditFileTool(); print('edit_file tool ok')"
```

- [ ] **Step 4: Commit**

```bash
git add py-agent/tools.py
git commit -m "feat: add edit_file search/replace tool"
```

---

### Task 2: Add ask_user tool (post-task pattern)

**Files:**
- Modify: `py-agent/tools.py`
- Modify: `src/main.rs`

- [ ] **Step 1: Add AskUserTool**

```python
class AskUserTool(Tool):
    """Ask the user a question. The answer will be available on the next task."""
    name = "ask_user"
    description = "Ask the user a question and get their response. The agent pauses and waits for user input."
    parameters = {
        "type": "object",
        "properties": {
            "question": {"type": "string", "description": "Question to ask the user"},
            "options": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional multiple-choice options",
            },
        },
        "required": ["question"],
    }

    def execute(self, question="", options=None, **kwargs) -> str:
        import os
        import json
        from datetime import datetime
        question_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents", "_ask_user.json")
        data = {
            "question": question,
            "options": options or [],
            "timestamp": datetime.now().isoformat(),
            "status": "pending",
        }
        with open(question_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return f"Question saved: {question}\nWaiting for user response..."
```

- [ ] **Step 2: Register**

```python
    registry.register(AskUserTool())
```

- [ ] **Step 3: Add Rust-side question handling**

In `src/main.rs`, add after `process_hire_requests`:

```rust
fn check_user_questions() {
    let question_path = std::path::Path::new("agents/_ask_user.json");
    if !question_path.exists() {
        return;
    }
    let content = match std::fs::read_to_string(question_path) {
        Ok(c) => c,
        Err(_) => return,
    };
    let question: serde_json::Value = match serde_json::from_str(&content) {
        Ok(v) => v,
        Err(_) => return,
    };
    let q_text = question.get("question").and_then(|v| v.as_str()).unwrap_or("?");
    let options = question.get("options").and_then(|v| v.as_array()).map(|a| {
        a.iter().filter_map(|v| v.as_str().map(|s| s.to_string())).collect::<Vec<_>>()
    }).unwrap_or_default();

    println!("\n[Question] {}", q_text);
    let answer = if !options.is_empty() {
        for (i, opt) in options.iter().enumerate() {
            println!("  {}. {}", i + 1, opt);
        }
        print!("Enter choice (1-{}): ", options.len());
        let _ = std::io::Write::flush(&mut std::io::stdout());
        let mut input = String::new();
        std::io::stdin().read_line(&mut input).ok();
        let input = input.trim().to_string();
        if let Ok(idx) = input.parse::<usize>() {
            if idx >= 1 && idx <= options.len() {
                options[idx - 1].clone()
            } else { input }
        } else { input }
    } else {
        print!("Your answer: ");
        let _ = std::io::Write::flush(&mut std::io::stdout());
        let mut input = String::new();
        std::io::stdin().read_line(&mut input).ok();
        input.trim().to_string()
    };

    // Write answer back
    let response = serde_json::json!({"question": q_text, "answer": answer, "status": "answered"});
    let _ = std::fs::write(question_path, serde_json::to_string_pretty(&response).unwrap());
    println!();
}
```

Wire into main.rs after `process_hire_requests`:

```rust
            check_user_questions();
```

- [ ] **Step 4: Build**

```bash
cargo build
```

- [ ] **Step 5: Commit**

```bash
git add py-agent/tools.py src/main.rs
git commit -m "feat: add edit_file and ask_user tools"
```
