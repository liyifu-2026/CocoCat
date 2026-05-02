# CocoCat Message Bus Architecture

The message bus is the central communication layer in CocoCat.

## Components
- Rust Core: spawns agents, routes messages
- JSON-RPC: line-delimited protocol over stdin/stdout
- Dispatch Queue: file-based async message passing
- Chat Log: append-only group.jsonl

## Flow
1. Leader calls dispatch_task tool
2. Tool writes JSON to agents/dispatch_queue/
3. Rust reads queue and forwards to target agent
4. Response is returned and logged to chat
