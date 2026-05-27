# Changelog

## 0.2.0 (2026-05-27)

### Phase 1: MCP Integration
- Added lightweight custom MCP (Model Context Protocol) implementation over stdio
- New modules: `metis.mcp.protocol`, `metis.mcp.client`, `metis.mcp.server`, `metis.mcp.spec`, `metis.mcp.errors`
- `MCPClient` supports connect, list_tools, call_tool, batch connection helper
- `MCPServer` exposes Metis tools via stdio JSON-RPC 2.0 transport
- `register_mcp_tools()` integrates MCP tools into `ToolRegistry` with namespaced names
- CLI `mcp-server` subcommand added
- Manifest supports `mcp_servers` configuration list

### Phase 2: HITL Approval System
- Added Human-in-the-Loop approval for destructive/credential/network operations
- New modules: `metis.hitl.core`, `metis.hitl.models`, `metis.hitl.rules`, `metis.hitl.store`
- `ApprovalRule` with flexible matching: tool names, side effects, permission levels, regex patterns, custom matchers
- Default approval rules cover destructive, credential, external_publish, shell_dangerous, network operations
- `HITLApprover` with async interactive prompt and configurable timeout
- `ApprovalStore` for pending/completed request tracking
- Integration via `TOOL_PRE_DISPATCH` hook in `ToolDispatcher`
- Manifest fields: `hitl_enabled`, `hitl_auto_approve_read_only`, `hitl_auto_approve_tools`, `hitl_auto_deny_tools`, `hitl_timeout_seconds`

### Phase 3: Intelligent Model Routing
- Added multi-provider routing with automatic failover
- New modules: `metis.routing.router`, `metis.routing.strategy`, `metis.routing.health`
- `ModelRouter` wraps multiple `BaseProvider` instances transparently
- `PrimaryFallbackStrategy` - always prefer highest-priority healthy provider
- `CapabilityMatchStrategy` - select provider best matching required capabilities
- `ProviderHealthMonitor` with configurable check intervals, failure thresholds, and automatic recovery
- Manifest fields: `providers`, `fallback_providers`, `routing_strategy`, `provider_health_check_interval`, `provider_failover_enabled`
- `_build_provider_for_manifest()` supports both single-provider and multi-provider modes

### Phase 4: Visualization
- Added trace and tool call visualization
- New modules: `metis.viz.trace_renderer`, `metis.viz.tool_flow`, `metis.viz.report`
- HTML timeline rendering with status-based color coding
- Mermaid sequence diagrams from trace events
- Mermaid flowcharts from tool call results
- ASCII timeline and flow diagrams for CLI output
- HTML report generator with summary cards, error panels, usage stats
- CLI `trace show` enhanced with `--html`, `--ascii`, `--mermaid` options
- CLI `trace report` generates HTML/JSON reports from session result JSON
- Web endpoints: `/api/v1/sessions/{id}/trace` and `/api/v1/sessions/{id}/report`

### Other Changes
- Updated `__version__` to 0.2.0
- `_manifest_fields()` preserves list/dict/bool/float types correctly
- `ToolDispatcher.TOOL_PRE_DISPATCH` hook now includes `spec` in context

## 0.1.0

- Initial release of Metis Agent Harness
