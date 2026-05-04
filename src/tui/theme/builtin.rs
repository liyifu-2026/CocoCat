use crate::theme::theme::{Theme, ThemeColors};

pub fn builtin_themes() -> Vec<Theme> {
    vec![
        Theme { name: "catppuccin-mocha".into(), colors: ThemeColors {
            background: "#1e1e2e".into(), surface: "#313244".into(), text: "#cdd6f4".into(),
            text_dim: "#6c7086".into(), accent: "#89b4fa".into(), success: "#a6e3a1".into(),
            error: "#f38ba8".into(), warning: "#fab387".into(), user_bubble: "#45475a".into(),
            agent_bubble: "#313244".into(), border: "#585b70".into(), selection: "#585b70".into(),
            scrollbar: "#45475a".into(), thinking: "#6c7086".into(), tool: "#89b4fa".into(),
            code_bg: "#181825".into(),
        }},
        Theme { name: "nord".into(), colors: ThemeColors {
            background: "#2e3440".into(), surface: "#3b4252".into(), text: "#eceff4".into(),
            text_dim: "#616e88".into(), accent: "#88c0d0".into(), success: "#a3be8c".into(),
            error: "#bf616a".into(), warning: "#d08770".into(), user_bubble: "#434c5e".into(),
            agent_bubble: "#3b4252".into(), border: "#4c566a".into(), selection: "#434c5e".into(),
            scrollbar: "#3b4252".into(), thinking: "#616e88".into(), tool: "#88c0d0".into(),
            code_bg: "#242933".into(),
        }},
        Theme { name: "dracula".into(), colors: ThemeColors {
            background: "#282a36".into(), surface: "#44475a".into(), text: "#f8f8f2".into(),
            text_dim: "#6272a4".into(), accent: "#bd93f9".into(), success: "#50fa7b".into(),
            error: "#ff5555".into(), warning: "#ffb86c".into(), user_bubble: "#44475a".into(),
            agent_bubble: "#363849".into(), border: "#6272a4".into(), selection: "#44475a".into(),
            scrollbar: "#44475a".into(), thinking: "#6272a4".into(), tool: "#bd93f9".into(),
            code_bg: "#21222c".into(),
        }},
        Theme { name: "tokyonight".into(), colors: ThemeColors {
            background: "#1a1b26".into(), surface: "#24283b".into(), text: "#a9b1d6".into(),
            text_dim: "#565f89".into(), accent: "#7aa2f7".into(), success: "#9ece6a".into(),
            error: "#f7768e".into(), warning: "#e0af68".into(), user_bubble: "#2f3348".into(),
            agent_bubble: "#24283b".into(), border: "#3b4261".into(), selection: "#2f3348".into(),
            scrollbar: "#24283b".into(), thinking: "#565f89".into(), tool: "#7aa2f7".into(),
            code_bg: "#13141f".into(),
        }},
        Theme { name: "gruvbox".into(), colors: ThemeColors {
            background: "#282828".into(), surface: "#3c3836".into(), text: "#ebdbb2".into(),
            text_dim: "#928374".into(), accent: "#83a598".into(), success: "#b8bb26".into(),
            error: "#fb4934".into(), warning: "#fe8019".into(), user_bubble: "#504945".into(),
            agent_bubble: "#3c3836".into(), border: "#665c54".into(), selection: "#504945".into(),
            scrollbar: "#3c3836".into(), thinking: "#928374".into(), tool: "#83a598".into(),
            code_bg: "#1d2021".into(),
        }},
    ]
}
