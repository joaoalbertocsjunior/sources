/// MCP server: exposes all registered adapters as resources and GitHub
/// write operations as tools, over a single `POST /mcp` JSON-RPC endpoint.
#[allow(dead_code)]

use std::collections::HashMap;
use std::net::SocketAddr;
use std::sync::{Arc, Mutex};

use axum::{extract::State, routing::post, Json, Router};
use base64::Engine as _;
use octocrab::models::IssueState;
use serde_json::{json, Value};

use crate::service::SourceService;

use super::protocol::{
    McpCapabilities, McpContent, McpError, McpErrorResponse, McpInitializeResult,
    McpRequest, McpResourceDef, McpResourcesCapability, McpResponse, McpServerInfo,
    McpToolAnnotations, McpToolDef, McpToolsCapability, ERR_INTERNAL, ERR_INVALID_PARAMS,
    ERR_METHOD_NOT_FOUND,
};

// ── GitHub adapter metadata ──────────────────────────────────────────────────

/// Metadata needed to perform GitHub write operations on behalf of an adapter.
#[derive(Debug, Clone)]
pub struct GithubAdapterMeta {
    /// GitHub org / user name.
    pub owner: String,
    /// Repository name (without owner prefix).
    pub repo: String,
    /// Optional personal-access token.  `None` → unauthenticated client.
    pub token: Option<String>,
}

// ── McpServer ────────────────────────────────────────────────────────────────

/// MCP server that wraps a [`SourceService`] and handles all MCP methods over
/// HTTP via a single `POST /mcp` JSON-RPC 2.0 endpoint.
///
/// # GitHub write tools
///
/// Before using any `github_*` tool, register the adapter's GitHub coordinates
/// with [`McpServer::register_github`].
pub struct McpServer {
    service: Arc<SourceService>,
    bind_addr: SocketAddr,
    /// GitHub metadata keyed by adapter ID.
    github_metas: Arc<Mutex<HashMap<String, GithubAdapterMeta>>>,
}

impl McpServer {
    /// Create a new `McpServer`.
    pub fn new(service: Arc<SourceService>, bind_addr: SocketAddr) -> Self {
        Self {
            service,
            bind_addr,
            github_metas: Arc::new(Mutex::new(HashMap::new())),
        }
    }

    /// Register GitHub coordinates for an adapter ID so write tools can find
    /// the right repo.
    pub fn register_github(
        &self,
        id: &str,
        owner: &str,
        repo: &str,
        token: Option<&str>,
    ) {
        let mut map = self.github_metas.lock().expect("github_metas lock poisoned");
        map.insert(
            id.to_owned(),
            GithubAdapterMeta {
                owner: owner.to_owned(),
                repo: repo.to_owned(),
                token: token.map(|t| t.to_owned()),
            },
        );
    }

    /// Build the axum `Router` (useful for testing without binding a port).
    pub fn router(&self) -> Router {
        let state = McpState {
            service: Arc::clone(&self.service),
            github_metas: Arc::clone(&self.github_metas),
        };
        Router::new()
            .route("/mcp", post(mcp_handler))
            .with_state(Arc::new(state))
    }

    /// Bind and serve.
    pub async fn serve(self) -> std::io::Result<()> {
        let addr = self.bind_addr;
        let router = self.router();
        let listener = tokio::net::TcpListener::bind(addr).await?;
        tracing::info!("McpServer listening on {addr}");
        axum::serve(listener, router).await
    }
}

// ── Shared handler state ─────────────────────────────────────────────────────

struct McpState {
    service: Arc<SourceService>,
    github_metas: Arc<Mutex<HashMap<String, GithubAdapterMeta>>>,
}

// ── Axum handler ─────────────────────────────────────────────────────────────

/// Single dispatcher for all MCP JSON-RPC requests on `POST /mcp`.
async fn mcp_handler(
    State(state): State<Arc<McpState>>,
    Json(req): Json<McpRequest>,
) -> Json<Value> {
    let id = req.id.clone();

    let result = match req.method.as_str() {
        "initialize" => handle_initialize(),
        "notifications/initialized" => Ok(json!({})),
        "tools/list" => handle_tools_list(),
        "tools/call" => handle_tools_call(&state, req.params).await,
        "resources/list" => handle_resources_list(&state),
        "resources/read" => handle_resources_read(&state, req.params).await,
        other => Err(McpError {
            code: ERR_METHOD_NOT_FOUND,
            message: format!("Method not found: {other}"),
        }),
    };

    Json(match result {
        Ok(value) => json!({
            "jsonrpc": "2.0",
            "id": id,
            "result": value,
        }),
        Err(err) => json!({
            "jsonrpc": "2.0",
            "id": id,
            "error": {
                "code": err.code,
                "message": err.message,
            },
        }),
    })
}

// ── initialize ───────────────────────────────────────────────────────────────

fn handle_initialize() -> Result<Value, McpError> {
    let result = McpInitializeResult {
        protocol_version: "2024-11-05".to_owned(),
        capabilities: McpCapabilities {
            tools: McpToolsCapability { list_changed: false },
            resources: McpResourcesCapability {
                subscribe: false,
                list_changed: false,
            },
        },
        server_info: McpServerInfo {
            name: "sources-lib".to_owned(),
            version: env!("CARGO_PKG_VERSION").to_owned(),
        },
    };
    serde_json::to_value(result).map_err(|e| McpError {
        code: ERR_INTERNAL,
        message: e.to_string(),
    })
}

// ── tools/list ───────────────────────────────────────────────────────────────

fn github_tools() -> Vec<McpToolDef> {
    vec![
        McpToolDef {
            name: "github_create_issue".to_owned(),
            description: "Create a new issue in a GitHub repository.".to_owned(),
            input_schema: json!({
                "type": "object",
                "required": ["source_id", "title", "body"],
                "properties": {
                    "source_id": {"type": "string", "description": "Registered adapter ID"},
                    "title":     {"type": "string"},
                    "body":      {"type": "string"},
                    "labels":    {"type": "array", "items": {"type": "string"}},
                }
            }),
            annotations: Some(McpToolAnnotations {
                read_only_hint: Some(false),
                destructive_hint: Some(false),
            }),
        },
        McpToolDef {
            name: "github_close_issue".to_owned(),
            description: "Close an existing issue.".to_owned(),
            input_schema: json!({
                "type": "object",
                "required": ["source_id", "issue_number"],
                "properties": {
                    "source_id":    {"type": "string"},
                    "issue_number": {"type": "integer"},
                    "reason":       {"type": "string"},
                }
            }),
            annotations: Some(McpToolAnnotations {
                read_only_hint: Some(false),
                destructive_hint: Some(false),
            }),
        },
        McpToolDef {
            name: "github_comment_on_issue".to_owned(),
            description: "Post a comment on an issue or pull request.".to_owned(),
            input_schema: json!({
                "type": "object",
                "required": ["source_id", "issue_number", "body"],
                "properties": {
                    "source_id":    {"type": "string"},
                    "issue_number": {"type": "integer"},
                    "body":         {"type": "string"},
                }
            }),
            annotations: Some(McpToolAnnotations {
                read_only_hint: Some(false),
                destructive_hint: Some(false),
            }),
        },
        McpToolDef {
            name: "github_create_pr".to_owned(),
            description: "Open a new pull request.".to_owned(),
            input_schema: json!({
                "type": "object",
                "required": ["source_id", "title", "body", "head", "base"],
                "properties": {
                    "source_id": {"type": "string"},
                    "title":     {"type": "string"},
                    "body":      {"type": "string"},
                    "head":      {"type": "string", "description": "The branch containing changes"},
                    "base":      {"type": "string", "description": "The branch to merge into"},
                }
            }),
            annotations: Some(McpToolAnnotations {
                read_only_hint: Some(false),
                destructive_hint: Some(false),
            }),
        },
        McpToolDef {
            name: "github_trigger_workflow".to_owned(),
            description: "Trigger a GitHub Actions workflow dispatch event.".to_owned(),
            input_schema: json!({
                "type": "object",
                "required": ["source_id", "workflow_id", "ref"],
                "properties": {
                    "source_id":   {"type": "string"},
                    "workflow_id": {"type": "string", "description": "Workflow filename or numeric ID"},
                    "ref":         {"type": "string", "description": "Branch or tag ref"},
                    "inputs":      {"type": "object"},
                }
            }),
            annotations: Some(McpToolAnnotations {
                read_only_hint: Some(false),
                destructive_hint: Some(false),
            }),
        },
        McpToolDef {
            name: "github_update_file".to_owned(),
            description: "Create or update a file in a GitHub repository.".to_owned(),
            input_schema: json!({
                "type": "object",
                "required": ["source_id", "path", "content", "message"],
                "properties": {
                    "source_id": {"type": "string"},
                    "path":      {"type": "string", "description": "File path in repo"},
                    "content":   {"type": "string", "description": "Plain-text file content"},
                    "message":   {"type": "string", "description": "Commit message"},
                    "branch":    {"type": "string"},
                }
            }),
            annotations: Some(McpToolAnnotations {
                read_only_hint: Some(false),
                destructive_hint: Some(false),
            }),
        },
        McpToolDef {
            name: "github_create_release".to_owned(),
            description: "Create a GitHub release.".to_owned(),
            input_schema: json!({
                "type": "object",
                "required": ["source_id", "tag", "name", "body"],
                "properties": {
                    "source_id": {"type": "string"},
                    "tag":       {"type": "string"},
                    "name":      {"type": "string"},
                    "body":      {"type": "string"},
                    "draft":     {"type": "boolean"},
                }
            }),
            annotations: Some(McpToolAnnotations {
                read_only_hint: Some(false),
                destructive_hint: Some(false),
            }),
        },
    ]
}

fn handle_tools_list() -> Result<Value, McpError> {
    Ok(json!({ "tools": github_tools() }))
}

// ── tools/call ───────────────────────────────────────────────────────────────

async fn handle_tools_call(state: &McpState, params: Value) -> Result<Value, McpError> {
    let tool_name = params
        .get("name")
        .and_then(|v| v.as_str())
        .ok_or_else(|| McpError {
            code: ERR_INVALID_PARAMS,
            message: "Missing 'name' in tools/call params".to_owned(),
        })?
        .to_owned();

    let args = params
        .get("arguments")
        .cloned()
        .unwrap_or(json!({}));

    let result = match tool_name.as_str() {
        "github_create_issue" => tool_create_issue(state, args).await,
        "github_close_issue" => tool_close_issue(state, args).await,
        "github_comment_on_issue" => tool_comment_on_issue(state, args).await,
        "github_create_pr" => tool_create_pr(state, args).await,
        "github_trigger_workflow" => tool_trigger_workflow(state, args).await,
        "github_update_file" => tool_update_file(state, args).await,
        "github_create_release" => tool_create_release(state, args).await,
        other => Err(format!("Unknown tool: {other}")),
    };

    match result {
        Ok(value) => Ok(json!({
            "content": [{"type": "text", "text": value.to_string()}],
            "isError": false,
        })),
        Err(msg) => Ok(json!({
            "content": [{"type": "text", "text": msg}],
            "isError": true,
        })),
    }
}

// ── resources/list ───────────────────────────────────────────────────────────

fn handle_resources_list(state: &McpState) -> Result<Value, McpError> {
    let ids = state.service.registry.list();
    let metas = state
        .github_metas
        .lock()
        .expect("github_metas lock poisoned");

    let mut resources: Vec<McpResourceDef> = Vec::new();

    for id in &ids {
        // All kinds expose an events resource.
        resources.push(McpResourceDef {
            uri: format!("sources://{id}/events"),
            name: format!("{id} — latest events"),
            description: Some("Latest synced source events".to_owned()),
            mime_type: Some("application/json".to_owned()),
        });

        // GitHub adapters additionally expose markdown files.
        if metas.contains_key(id.as_str()) {
            resources.push(McpResourceDef {
                uri: format!("sources://{id}/agents-md"),
                name: format!("{id} — AGENTS.md"),
                description: Some("AGENTS.md from the GitHub repository".to_owned()),
                mime_type: Some("text/plain".to_owned()),
            });
            resources.push(McpResourceDef {
                uri: format!("sources://{id}/skill-md"),
                name: format!("{id} — SKILL.md"),
                description: Some("SKILL.md from the GitHub repository".to_owned()),
                mime_type: Some("text/plain".to_owned()),
            });
        }
    }

    Ok(json!({ "resources": resources }))
}

// ── resources/read ───────────────────────────────────────────────────────────

async fn handle_resources_read(state: &McpState, params: Value) -> Result<Value, McpError> {
    let uri = params
        .get("uri")
        .and_then(|v| v.as_str())
        .ok_or_else(|| McpError {
            code: ERR_INVALID_PARAMS,
            message: "Missing 'uri' in resources/read params".to_owned(),
        })?
        .to_owned();

    // Parse URI: sources://{id}/{resource}
    let stripped = uri
        .strip_prefix("sources://")
        .ok_or_else(|| McpError {
            code: ERR_INVALID_PARAMS,
            message: format!("Unsupported URI scheme: {uri}"),
        })?;

    let (adapter_id, resource) = stripped.split_once('/').ok_or_else(|| McpError {
        code: ERR_INVALID_PARAMS,
        message: format!("Invalid URI format: {uri}"),
    })?;

    // Check adapter exists.
    let known = state.service.registry.list();
    if !known.contains(&adapter_id.to_owned()) {
        return Err(McpError {
            code: ERR_INVALID_PARAMS,
            message: format!("Resource not found: {uri}"),
        });
    }

    let text = match resource {
        "events" => {
            // Trigger a sync and return events as JSON.
            let results = state.service.registry.sync_all().await;
            let events: Vec<Value> = results
                .into_iter()
                .flat_map(|r| r.unwrap_or_default())
                .map(|e| serde_json::to_value(e).unwrap_or(json!(null)))
                .collect();
            json!(events).to_string()
        }
        "agents-md" => fetch_github_file(state, adapter_id, "AGENTS.md").await?,
        "skill-md" => fetch_github_file(state, adapter_id, "SKILL.md").await?,
        other => {
            return Err(McpError {
                code: ERR_INVALID_PARAMS,
                message: format!("Resource not found: {uri} (unknown sub-resource '{other}')"),
            });
        }
    };

    Ok(json!({
        "contents": [{
            "uri": uri,
            "mimeType": "text/plain",
            "text": text,
        }]
    }))
}

// ── GitHub helpers ────────────────────────────────────────────────────────────

/// Look up GitHub metadata for a given adapter ID.
fn get_meta(state: &McpState, source_id: &str) -> Result<GithubAdapterMeta, String> {
    let map = state.github_metas.lock().expect("github_metas lock poisoned");
    map.get(source_id)
        .cloned()
        .ok_or_else(|| format!("No GitHub metadata registered for source_id '{source_id}'"))
}

/// Build an Octocrab client (authenticated if a token is present).
fn build_octocrab(meta: &GithubAdapterMeta) -> Result<octocrab::Octocrab, String> {
    match &meta.token {
        Some(tok) => octocrab::OctocrabBuilder::new()
            .personal_token(tok.clone())
            .build()
            .map_err(|e| e.to_string()),
        None => Ok(octocrab::Octocrab::default()),
    }
}

/// Fetch a file from GitHub and return its decoded text content.
/// Returns an empty string if the file does not exist (404).
async fn fetch_github_file(
    state: &McpState,
    adapter_id: &str,
    path: &str,
) -> Result<String, McpError> {
    let meta = {
        let map = state.github_metas.lock().expect("github_metas lock poisoned");
        map.get(adapter_id).cloned()
    };

    let meta = match meta {
        Some(m) => m,
        None => {
            return Err(McpError {
                code: ERR_INVALID_PARAMS,
                message: format!(
                    "No GitHub metadata registered for adapter '{adapter_id}'"
                ),
            });
        }
    };

    let octo = build_octocrab(&meta).map_err(|e| McpError {
        code: ERR_INTERNAL,
        message: e,
    })?;

    let result = octo
        .repos(&meta.owner, &meta.repo)
        .get_content()
        .path(path)
        .send()
        .await;

    match result {
        Ok(contents) => {
            // The response is a `octocrab::models::repos::ContentItems`.
            // Extract the first item's content (base64 encoded).
            let text = contents
                .items
                .into_iter()
                .next()
                .and_then(|item| item.content)
                .map(|encoded| {
                    // GitHub wraps lines at 60 chars with \n — strip whitespace.
                    let clean: String = encoded.chars().filter(|c| !c.is_whitespace()).collect();
                    base64::engine::general_purpose::STANDARD
                        .decode(clean)
                        .ok()
                        .and_then(|bytes| String::from_utf8(bytes).ok())
                        .unwrap_or_default()
                })
                .unwrap_or_default();
            Ok(text)
        }
        Err(octocrab::Error::GitHub { source, .. })
            if source.message.contains("Not Found") || source.message.contains("404") =>
        {
            Ok(String::new())
        }
        Err(e) => Err(McpError {
            code: ERR_INTERNAL,
            message: e.to_string(),
        }),
    }
}

// ── Tool handlers ─────────────────────────────────────────────────────────────

/// Create a GitHub issue.
async fn tool_create_issue(state: &McpState, args: Value) -> Result<Value, String> {
    let source_id = args["source_id"].as_str().ok_or("Missing source_id")?;
    let title = args["title"].as_str().ok_or("Missing title")?;
    let body = args["body"].as_str().ok_or("Missing body")?;
    let labels: Vec<String> = args["labels"]
        .as_array()
        .map(|arr| {
            arr.iter()
                .filter_map(|v| v.as_str().map(|s| s.to_owned()))
                .collect()
        })
        .unwrap_or_default();

    let meta = get_meta(state, source_id)?;
    let octo = build_octocrab(&meta)?;

    let issues_handler = octo.issues(&meta.owner, &meta.repo);
    let mut builder = issues_handler.create(title).body(body);
    if !labels.is_empty() {
        builder = builder.labels(labels);
    }

    let issue = builder.send().await.map_err(|e| e.to_string())?;
    Ok(json!({
        "number": issue.number,
        "url": issue.html_url.to_string(),
    }))
}

/// Close an existing GitHub issue.
async fn tool_close_issue(state: &McpState, args: Value) -> Result<Value, String> {
    let source_id = args["source_id"].as_str().ok_or("Missing source_id")?;
    let issue_number = args["issue_number"]
        .as_u64()
        .ok_or("Missing or invalid issue_number")?;

    let meta = get_meta(state, source_id)?;
    let octo = build_octocrab(&meta)?;

    let issue = octo
        .issues(&meta.owner, &meta.repo)
        .update(issue_number)
        .state(IssueState::Closed)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    Ok(json!({
        "number": issue.number,
        "state": "closed",
    }))
}

/// Post a comment on an issue or pull request.
async fn tool_comment_on_issue(state: &McpState, args: Value) -> Result<Value, String> {
    let source_id = args["source_id"].as_str().ok_or("Missing source_id")?;
    let issue_number = args["issue_number"]
        .as_u64()
        .ok_or("Missing or invalid issue_number")?;
    let body = args["body"].as_str().ok_or("Missing body")?;

    let meta = get_meta(state, source_id)?;
    let octo = build_octocrab(&meta)?;

    let comment = octo
        .issues(&meta.owner, &meta.repo)
        .create_comment(issue_number, body)
        .await
        .map_err(|e| e.to_string())?;

    Ok(json!({
        "id": comment.id,
        "url": comment.html_url.to_string(),
    }))
}

/// Open a new pull request.
async fn tool_create_pr(state: &McpState, args: Value) -> Result<Value, String> {
    let source_id = args["source_id"].as_str().ok_or("Missing source_id")?;
    let title = args["title"].as_str().ok_or("Missing title")?;
    let body = args["body"].as_str().ok_or("Missing body")?;
    let head = args["head"].as_str().ok_or("Missing head")?;
    let base = args["base"].as_str().ok_or("Missing base")?;

    let meta = get_meta(state, source_id)?;
    let octo = build_octocrab(&meta)?;

    let pr = octo
        .pulls(&meta.owner, &meta.repo)
        .create(title, head, base)
        .body(body)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    Ok(json!({
        "number": pr.number,
        "url": pr.html_url.map(|u| u.to_string()).unwrap_or_default(),
    }))
}

/// Trigger a GitHub Actions workflow dispatch event.
async fn tool_trigger_workflow(state: &McpState, args: Value) -> Result<Value, String> {
    let source_id = args["source_id"].as_str().ok_or("Missing source_id")?;
    let workflow_id = args["workflow_id"].as_str().ok_or("Missing workflow_id")?;
    let ref_name = args["ref"].as_str().ok_or("Missing ref")?;
    let inputs = args["inputs"].clone();

    let meta = get_meta(state, source_id)?;
    let octo = build_octocrab(&meta)?;

    let actions = octo.actions();
    let mut dispatch =
        actions.create_workflow_dispatch(&meta.owner, &meta.repo, workflow_id, ref_name);

    if !inputs.is_null() {
        dispatch = dispatch.inputs(inputs);
    }

    dispatch.send().await.map_err(|e| e.to_string())?;

    Ok(json!({ "status": "triggered" }))
}

/// Create or update a file in a GitHub repository.
async fn tool_update_file(state: &McpState, args: Value) -> Result<Value, String> {
    let source_id = args["source_id"].as_str().ok_or("Missing source_id")?;
    let path = args["path"].as_str().ok_or("Missing path")?;
    let content = args["content"].as_str().ok_or("Missing content")?;
    let message = args["message"].as_str().ok_or("Missing message")?;
    let branch = args["branch"].as_str();

    let meta = get_meta(state, source_id)?;
    let octo = build_octocrab(&meta)?;

    // Try to get the current file SHA (needed for updates).
    let existing_sha: Option<String> = {
        let result = octo
            .repos(&meta.owner, &meta.repo)
            .get_content()
            .path(path)
            .send()
            .await;
        match result {
            Ok(items) => items
                .items
                .into_iter()
                .next()
                .map(|item| item.sha),
            Err(_) => None,
        }
    };

    let encoded =
        base64::engine::general_purpose::STANDARD.encode(content.as_bytes());

    // Build the request body manually since octocrab's file update API
    // varies by version — use the raw REST route for reliability.
    let route = format!("/repos/{}/{}/contents/{}", meta.owner, meta.repo, path);
    let mut body = json!({
        "message": message,
        "content": encoded,
    });
    if let Some(sha) = existing_sha {
        body["sha"] = json!(sha);
    }
    if let Some(br) = branch {
        body["branch"] = json!(br);
    }

    let resp: Value = octo
        .put(&route, Some(&body))
        .await
        .map_err(|e| e.to_string())?;

    let sha = resp["content"]["sha"]
        .as_str()
        .unwrap_or("")
        .to_owned();

    Ok(json!({ "path": path, "sha": sha }))
}

/// Create a GitHub release.
async fn tool_create_release(state: &McpState, args: Value) -> Result<Value, String> {
    let source_id = args["source_id"].as_str().ok_or("Missing source_id")?;
    let tag = args["tag"].as_str().ok_or("Missing tag")?;
    let name = args["name"].as_str().ok_or("Missing name")?;
    let body = args["body"].as_str().ok_or("Missing body")?;
    let draft = args["draft"].as_bool().unwrap_or(false);

    let meta = get_meta(state, source_id)?;
    let octo = build_octocrab(&meta)?;

    let release = octo
        .repos(&meta.owner, &meta.repo)
        .releases()
        .create(tag)
        .name(name)
        .body(body)
        .draft(draft)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    Ok(json!({
        "id": release.id,
        "url": release.html_url.to_string(),
    }))
}

// ── suppress unused-import warning for McpContent (used in doc/spec) ─────────
const _: fn() = || {
    let _ = McpContent::Text { text: String::new() };
    let _ = McpResponse { jsonrpc: String::new(), id: None, result: json!(null) };
    let _ = McpErrorResponse {
        jsonrpc: String::new(),
        id: None,
        error: McpError { code: 0, message: String::new() },
    };
    let _ = McpResourceDef {
        uri: String::new(),
        name: String::new(),
        description: None,
        mime_type: None,
    };
};
