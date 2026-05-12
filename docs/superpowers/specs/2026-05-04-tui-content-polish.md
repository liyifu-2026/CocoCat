# TUI Content Polish — Markdown + Spinner + Syntax Hover

## 1. Markdown 渲染

**现状：** delta 事件文本直接用 `Span::raw()` 输出，纯文本。

**改法：** 用 `comrak` 解析 delta 文本为 AST，转换成 ratatui `Vec<Span>` 序列。

支持：
- `**粗体**` → `Style::default().add_modifier(Modifier::BOLD)`
- `*斜体*` → `Style::default().add_modifier(Modifier::ITALIC)`
- `` `代码` `` → `Style::default().fg(theme.accent_color())`
- `> 引用` → 左侧竖线 + 灰色
- `- 列表` → `•` 前缀
- 行内代码和代码块

渲染方式：`build_message_lines` 中遇到 `Delta(text)` 时，调用 `render_markdown(text) -> Vec<Span>`。

## 2. 代码语法高亮

**现状：** 无。

**改法：** 用已安装的 `syntect` crate，解析代码块中的语言并着色。

代码块检测：
- `` ```python `` → 用 syntect 的 Python 语法定义高亮
- `` ``` `` → 自动检测或默认文本高亮

syntect 用法：
```rust
use syntect::parsing::SyntaxSet;
use syntect::highlighting::ThemeSet;
use syntect::html::highlighted_html_for_string;

let ss = SyntaxSet::load_defaults_newlines();
let ts = ThemeSet::load_defaults();
let syntax = ss.find_syntax_by_token("python").unwrap();
let highlighted = syntect::easy::HighlightLines::new(syntax, &ts.themes["base16-ocean.dark"]);
```
然后 mapping syntect 的 `Style` 到 ratatui `Style`。

## 3. 流式 Spinner

**现状：** 无状态指示，输入后等待无反馈。

**改法：** 在 input_bar 元数据行末尾，当 `is_streaming == true` 时显示动画字符。

字符序列：`◌ ◯ ● ○`（旋转）
每帧（100ms）切换下一个。

实现：
```rust
// input_bar 渲染时
if is_streaming {
    let frame = (std::time::... / 100) % 4;
    let spinner = ["◌", "◯", "●", "○"][frame];
    // append to metadata line
}
```

## 4. 悬停变色效果

**现状：** 无鼠标交互反馈。

**改法：** 在 main.rs 中跟踪鼠标位置（`Event::Mouse(MouseEventKind::Moved)`），将坐标传入 `render_chat_panel`。当某条消息行被 hover 时，改变该行的 `bg`。

简化实现：
- 跟踪 `hovered_row: Option<u16>`（鼠标所在的终端行）
- 在 `build_message_lines` 中，如果 line index == hovered_row，添加 `bg(backgroundElement)`
