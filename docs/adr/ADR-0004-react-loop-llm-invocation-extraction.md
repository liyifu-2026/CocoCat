# ADR-0004: ReAct loop LLM invocation extraction

**Date:** 2026-05-19
**Status:** accepted

**Context:** `run_agent()` was a 200-line function with duplicated streaming and non-streaming branches (~30 lines each, nearly identical logic). Adding a third invocation mode (batch, hybrid) would require touching the loop.

**Decision:** Extracted `_invoke_llm()` — one async function that returns `(content, tool_calls, reasoning)` regardless of whether the LLM streams or not. The ReAct loop body shrank from 50+ lines to 15 lines: call `_invoke_llm` → handle tool calls → repeat.

**Consequences:** Loop logic is independent of LLM invocation strategy. New invocation modes are adapters at the `_invoke_llm` seam. Loop itself becomes testable with a mock LLM that returns pre-canned responses.
