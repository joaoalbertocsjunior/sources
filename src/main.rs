use std::sync::Arc;

use sources_lib::{HttpControlServer, KindRegistry, RpcServer, SourceRegistry, SourceService, Store};

/// Parse a flag of the form `--flag value` from the args iterator.
fn flag(args: &[String], name: &str) -> Option<String> {
    args.windows(2)
        .find(|w| w[0] == name)
        .map(|w| w[1].clone())
}

fn has(args: &[String], name: &str) -> bool {
    args.iter().any(|a| a == name)
}

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::try_from_default_env()
                .unwrap_or_else(|_| "sources=info".into()),
        )
        .init();

    let args: Vec<String> = std::env::args().collect();

    if has(&args, "--help") || has(&args, "-h") {
        println!(
            "sources — standalone adapter runtime\n\
             \n\
             USAGE:\n\
             \x20  sources [OPTIONS]\n\
             \n\
             OPTIONS:\n\
             \x20  --m2m  ADDR   JSON-RPC 2.0 listen address  [default: 0.0.0.0:7000]\n\
             \x20  --http ADDR   HTTP control plane address    [default: 0.0.0.0:8080]\n\
             \x20  --data DIR    Persistence directory         [optional]\n\
             \x20  --no-m2m      Disable the JSON-RPC server\n\
             \x20  --no-http     Disable the HTTP control server\n\
             \x20  --help        Show this message\n\
             \n\
             ENV:\n\
             \x20  RUST_LOG      Log filter (e.g. sources=debug)"
        );
        return;
    }

    let m2m_addr: std::net::SocketAddr = flag(&args, "--m2m")
        .unwrap_or_else(|| "0.0.0.0:7000".into())
        .parse()
        .expect("invalid --m2m address");

    let http_addr: std::net::SocketAddr = flag(&args, "--http")
        .unwrap_or_else(|| "0.0.0.0:8080".into())
        .parse()
        .expect("invalid --http address");

    let no_m2m = has(&args, "--no-m2m");
    let no_http = has(&args, "--no-http");

    let registry = Arc::new(SourceRegistry::new());
    let kinds = KindRegistry::new();

    let service: Arc<SourceService> = if let Some(dir) = flag(&args, "--data") {
        let store = Arc::new(Store::open(&dir).expect("failed to open data store"));
        Arc::new(SourceService::new(registry, kinds).with_store(store))
    } else {
        Arc::new(SourceService::new(registry, kinds))
    };

    match (no_m2m, no_http) {
        (true, true) => {
            tracing::warn!("both --no-m2m and --no-http set — nothing to serve");
        }
        (true, false) => {
            HttpControlServer::new(Arc::clone(&service), http_addr)
                .serve()
                .await
                .expect("HTTP server error");
        }
        (false, true) => {
            let m2m = RpcServer::new(m2m_addr);
            m2m.wire_service(Arc::clone(&service)).await;
            m2m.serve().await.expect("M2M server error");
        }
        (false, false) => {
            let m2m = RpcServer::new(m2m_addr);
            m2m.wire_service(Arc::clone(&service)).await;
            tokio::try_join!(
                m2m.serve(),
                HttpControlServer::new(Arc::clone(&service), http_addr).serve(),
            )
            .expect("server error");
        }
    }
}
