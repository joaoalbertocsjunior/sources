/// Source adapter that pulls resources from an upstream MCP server.
///
/// On every [`sync`] call it lists available resources from the remote MCP
/// server and fetches each one, emitting a `mcp.resource` [`SourceEvent`] per
/// resource.  If the remote server is unreachable the adapter returns an empty
/// event list rather than propagating the error.
#[allow(dead_code)]

use async_trait::async_trait;
use serde_json::json;

use crate::adapter::{AdapterError, SourceAdapter, SourceEvent};

/// Adapter that connects to an upstream MCP server and pulls its resources as
/// source events.
pub struct McpServerAdapter {
    id: String,
    /// Base URL of the upstream MCP server (e.g. `http://localhost:3000`).
    url: String,
    client: reqwest::Client,
}

impl McpServerAdapter {
    /// Create a new adapter.
    ///
    /// * `id`  — unique adapter ID used in emitted events.
    /// * `url` — base URL of the upstream MCP server (`POST {url}/mcp`).
    pub fn new(id: impl Into<String>, url: impl Into<String>) -> Self {
        Self {
            id: id.into(),
            url: url.into(),
            client: reqwest::Client::new(),
        }
    }

    /// POST a JSON-RPC 2.0 request to the upstream server's `/mcp` endpoint.
    async fn rpc_call(
        &self,
        id: u32,
        method: &str,
        params: serde_json::Value,
    ) -> Result<serde_json::Value, String> {
        let endpoint = format!("{}/mcp", self.url);
        let body = json!({
            "jsonrpc": "2.0",
            "id": id,
            "method": method,
            "params": params,
        });

        let resp = self
            .client
            .post(&endpoint)
            .json(&body)
            .send()
            .await
            .map_err(|e| e.to_string())?;

        let json: serde_json::Value = resp.json().await.map_err(|e| e.to_string())?;
        Ok(json)
    }
}

#[async_trait]
impl SourceAdapter for McpServerAdapter {
    fn id(&self) -> &str {
        &self.id
    }

    fn kind(&self) -> &str {
        "mcp_server"
    }

    async fn sync(&mut self) -> Result<Vec<SourceEvent>, AdapterError> {
        // Step 1: list resources.
        let list_resp = match self.rpc_call(1, "resources/list", json!({})).await {
            Ok(r) => r,
            Err(_) => return Ok(vec![]), // server unreachable — degrade gracefully
        };

        let uris: Vec<String> = list_resp["result"]["resources"]
            .as_array()
            .map(|arr| {
                arr.iter()
                    .filter_map(|r| r.get("uri")?.as_str().map(|s| s.to_owned()))
                    .collect()
            })
            .unwrap_or_default();

        let now = unix_now();
        let mut events = Vec::with_capacity(uris.len());

        // Step 2: fetch each resource individually.
        for uri in uris {
            let read_resp = match self
                .rpc_call(2, "resources/read", json!({ "uri": uri }))
                .await
            {
                Ok(r) => r,
                Err(_) => continue, // skip unreachable resources
            };

            // Extract text content from the first content item.
            let content = read_resp["result"]["contents"]
                .as_array()
                .and_then(|arr| arr.first())
                .and_then(|item| item.get("text"))
                .and_then(|t| t.as_str())
                .unwrap_or("")
                .to_owned();

            events.push(SourceEvent {
                source_id: self.id.clone(),
                kind: "mcp.resource".to_owned(),
                payload: json!({
                    "uri": uri,
                    "content": content,
                    "source_server": self.url,
                }),
                at_unix: now,
            });
        }

        Ok(events)
    }
}

fn unix_now() -> f64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs_f64())
        .unwrap_or(0.0)
}
