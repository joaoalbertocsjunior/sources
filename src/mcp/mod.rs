/// MCP (Model Context Protocol) server implementation.
///
/// Exposes sources-lib adapters as MCP resources and GitHub write operations
/// as MCP tools, following the JSON-RPC 2.0 / MCP 2024-11-05 specification.
pub mod protocol;
pub mod server;

pub use server::McpServer;
