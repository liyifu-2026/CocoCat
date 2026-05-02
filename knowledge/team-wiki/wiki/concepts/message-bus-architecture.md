```yaml
---
type: concept
title: Message Bus Architecture
created: 2026-05-03
sources:
  - message-bus-architecture.md
tags: []
related: []
---
# Message Bus Architecture

## Overview

The Message Bus Architecture is a core communication pattern within the [CocoCat](../entities/cococat.md) multi-agent system. It provides a centralized, asynchronous message-passing layer that connects all agents, the Rust core, and external systems. This architecture ensures loose coupling, reliability, and traceability of all inter-agent interactions.

The message bus is implemented in Rust, leveraging JSON-RPC for structured message transport, a dispatch queue for ordering, and a chat log for full audit trails.

## Key Components

- **Rust Core** – The backbone of the system. Manages agent processes, routes messages, and maintains the bus lifecycle. The core implements message validation, delivery guarantees, and integration with the agent registry.
- **JSON-RPC** – The wire protocol for all messages on the bus. Each message is formatted as a JSON-RPC request (or notification) with a method name (e.g., `dispatch_task`, `agent_response`) and parameters. This standardizes agent-to-agent and agent-to-core communication.
- **Dispatch Queue** – An internal queue inside the Rust core that holds incoming messages before routing. It handles ordering, deduplication, and retry logic. The queue ensures that messages are processed in the order they are received and prevents race conditions.
- **Chat Log** – A persistent log of all messages that flow through the bus. Each message is recorded with timestamps, sender, receiver, method, and payload. The chat log serves as both an audit trail and a source of truth for debugging and replay.

## Message Flow

1. **Leader Task Invocation** – A human or an agent (e.g., Team Leader) sends a task request via the message bus using the `dispatch_task` method.
2. **JSON-RPC Encoding** – The task request is serialized into a JSON-RPC object and sent to the Rust core.
3. **Dispatch Queue Processing** – The core places the request into the dispatch queue. The queue ensures the request is processed after any earlier messages.
4. **Agent Resolution & Routing** – The Rust core resolves the target agent (or agents) via the AgentRegistry, then forwards the message to the appropriate agent process.
5. **Agent Response** – The target agent processes the task and sends back a response (or an error) through the bus, again as JSON-RPC.
6. **Response Logging** – The core logs both the request and the response to the Chat Log for future reference.
7. **Delivery to Caller** – The response is returned to the original caller, completing the round trip.

This flow ensures every message is traceable, ordered, and persisted.

## Relation to Multi-Agent Systems

The message bus implements the **Message Passing** principle defined in [Multi-Agent Systems](../concepts/multi-agent-systems.md). It enables:

- **Single Responsibility** – Each agent only needs to know how to send and receive messages on the bus, not the details of other agents.
- **Scene Isolation** – Scenes can be associated with separate bus channels or filters, ensuring agents within a scene only see relevant messages.
- **Human Oversight** – The Team Leader agent can monitor all bus traffic through the Chat Log, and can inject or redirect tasks as needed.

## Benefits

- **Loose Coupling** – Agents are independent; they communicate only through the bus.
- **Scalability** – The bus can handle many concurrent messages across distributed agents.
- **Reliability** – The dispatch queue and JSON-RPC format provide retry, error handling, and message validation.
- **Observability** – The Chat Log gives full visibility into all agent interactions, aiding debugging and compliance.

## Related Concepts

- [Multi-Agent Systems](../concepts/multi-agent-systems.md) – The overarching pattern that relies on message bus communication.
- [CocoCat](../entities/cococat.md) – The system that implements this architecture.