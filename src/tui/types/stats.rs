#[derive(Debug, Clone, Default)]
pub struct ToolStats {
    pub tool_calls: Vec<ToolCallInfo>,
}

#[derive(Debug, Clone)]
pub struct ToolCallInfo {
    pub name: String,
    pub status: String,
    pub count: u32,
}

#[derive(Debug, Clone, Default)]
pub struct SessionStats {
    pub message_count: usize,
    pub token_count: u32,
    pub token_limit: u32,
    pub agent_name: String,
}

#[derive(Debug, Clone, Default)]
pub struct SystemStats {
    pub unread_mail: u32,
    pub pending_dispatches: u32,
}
