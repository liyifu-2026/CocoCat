# 搜索路由器设计

## 问题
`web_search` 工具硬编码了 DuckDuckGo API，大陆用户无法使用。

## 方案
多后端 SearchRouter，失败自动降级，无需心跳/探活。

## 架构

```
py-agent/tools/search/
├── __init__.py        # SearchRouter
├── base.py            # SearchBackend 抽象类
└── backends/
    ├── baidu.py       # 百度 (scrape HTML)
    ├── bing.py        # 必应 (scrape HTML)
    └── duckduckgo.py  # DuckDuckGo API (现有逻辑迁移)
```

## 核心设计

### SearchBackend
```python
class SearchBackend:
    name: str
    order: int       # 默认优先级顺序
    def search(query, max_results) -> str
```

### SearchRouter
- 无心跳、无启动探活
- 按 (失败次数, order) 排序后端
- 连续失败 3 次 → 跳过（5分钟后重置）
- 对 WebSearchTool 透明

### 失败降级
```
一次搜索:
  Baidu.search() → ❌ 不通 → failures=1, 试下一个
  Bing.search()  → ✅ 通   → 返回结果

Baidu 连续失败 3 次 → 本轮跳过
5分钟后失败计数器重置 → 再给它一次机会
```
