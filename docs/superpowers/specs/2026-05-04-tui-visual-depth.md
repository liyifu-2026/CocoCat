# TUI Visual Depth — Background Layering + Spacing

**改法：**

1. header / input_bar / status_bar / sidebar → `bg(backgroundPanel)`（比根背景亮一级）
2. 区块之间留 1 行空白（用 `Constraint::Length(1)` 在 layout 中插入间隔）
3. chat 区域保持透明（默认终端背景）
4. input_bar 保留左侧 accent 竖条
5. sidebar 移除 Block 背景，直接 `Style::default().bg(theme.surface())`

**Layout 改动（main.rs）：**
```
Constraint::Length(1),   // header bg=surface
Constraint::Length(1),   // GAP: 空白行
Constraint::Min(3),      // chat bg=透明
Constraint::Length(4),   // input bg=surface + 左竖条
Constraint::Length(1),   // GAP: 空白行
Constraint::Length(1),   // status bg=surface
```

**header.rs / input_bar.rs / status_bar.rs / sidebar.rs：**
- 统一用 `Block::default().style(Style::default().bg(theme.surface()))`
- 无边框
- input_bar 额外加 `Borders::LEFT` accent 竖条
