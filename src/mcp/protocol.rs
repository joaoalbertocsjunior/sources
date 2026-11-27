/// MCP protocol types following JSON-RPC 2.0 / MCP 2024-11-05 specification.
use serde::{Deserialize, Serialize};
use serde_json::Value;

/// Generic JSON-RPC 2.0 request envelope.
#[derive(Debug, Deserialize)]
pub struct McpRequest {
    pub jsonrpc: String,
    pub id: Option<Value>,
    pub method: String,
    #[serde(default)]
    pub params: Value,
}

/// Successful JSON-RPC 2.0 response.
#[derive(Debug, Serialize)]
pub struct McpResponse {
    pub jsonrpc: String,
    pub id: Option<Value>,
    pub result: Value,
}

/// Error JSON-RPC 2.0 response.
#[derive(Debug, Serialize)]
pub struct McpErrorResponse {
    pub jsonrpc: String,
    pub id: Option<Value>,
    pub error: McpError,
}

/// JSON-RPC error object.
#[derive(Debug, Serialize)]
pub struct McpError {
    pub code: i32,
    pub message: String,
}

/// MCP tool definition (returned in `tools/list`).
#[derive(Debug, Clone, Serialize)]
pub struct McpToolDef {
    pub name: String,
    pub description: String,
    #[serde(rename = "inputSchema")]
    pub input_schema: Value,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub annotations: Option<McpToolAnnotations>,
}

/// Optional hints about a tool's behavior.
#[derive(Debug, Clone, Serialize)]
pub struct McpToolAnnotations {
    #[serde(rename = "readOnlyHint", skip_serializing_if = "Option::is_none")]
    pub read_only_hint: Option<bool>,
    #[serde(rename = "destructiveHint", skip_serializing_if = "Option::is_none")]
    pub destructive_hint: Option<bool>,
}

/// MCP resource definition (returned in `resources/list`).
#[derive(Debug, Clone, Serialize)]
pub struct McpResourceDef {
    pub uri: String,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(rename = "mimeType", skip_serializing_if = "Option::is_none")]
    pub mime_type: Option<String>,
}

/// Content item returned from tool calls and resource reads.
#[derive(Debug, Serialize)]
#[serde(tag = "type", rename_all = "lowercase")]
pub enum McpContent {
    Text { text: String },
}

/// Result of the `initialize` method.
#[derive(Debug, Serialize)]
pub struct McpInitializeResult {
    #[serde(rename = "protocolVersion")]
    pub protocol_version: String,
    pub capabilities: McpCapabilities,
    #[serde(rename = "serverInfo")]
    pub server_info: McpServerInfo,
}

/// Server capability declarations.
#[derive(Debug, Serialize)]
pub struct McpCapabilities {
    pub tools: McpToolsCapability,
    pub resources: McpResourcesCapability,
}

/// Tools capability flags.
#[derive(Debug, Serialize)]
pub struct McpToolsCapability {
    #[serde(rename = "listChanged")]
    pub list_changed: bool,
}

/// Resources capability flags.
#[derive(Debug, Serialize)]
pub struct McpResourcesCapability {
    pub subscribe: bool,
    #[serde(rename = "listChanged")]
    pub list_changed: bool,
}

/// Server identity block.
#[derive(Debug, Serialize)]
pub struct McpServerInfo {
    pub name: String,
    pub version: String,
}

// JSON-RPC 2.0 standard error codes.
pub const ERR_INVALID_REQUEST: i32 = -32600;
pub const ERR_METHOD_NOT_FOUND: i32 = -32601;
pub const ERR_INVALID_PARAMS: i32 = -32602;
pub const ERR_INTERNAL: i32 = -32603;
