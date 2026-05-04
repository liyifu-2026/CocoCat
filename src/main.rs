use tracing_subscriber::EnvFilter;

mod agent;
mod api;
mod config;
mod db;
mod dispatch;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .init();

    tracing::info!("CocoCat v2 starting...");

    let db_pool = db::pool::create_pool()?;
    db::pool::run_migrations(&db_pool)?;
    config::seed_from_config_toml(&db_pool)?;

    let agents = db::agents::load_agents(&db_pool)?;
    tracing::info!("Loaded {} agents", agents.len());

    let agent_manager = std::sync::Arc::new(agent::manager::AgentManager::new(db_pool.clone()));
    for agent_config in &agents {
        agent_manager.spawn(agent_config).await;
    }

    // Spawn health check loop in background
    let hc_manager = agent_manager.clone();
    tokio::spawn(async move {
        hc_manager.health_check_loop().await;
    });

    let (task_tx, task_rx) = tokio::sync::mpsc::channel::<dispatch::engine::TaskEvent>(256);
    let mut dispatch_engine = dispatch::engine::DispatchEngine::new(
        db_pool.clone(),
        agent_manager.clone(),
        task_rx,
    );

    let app_state = api::router::AppState {
        db_pool: db_pool.clone(),
        task_tx: task_tx.clone(),
    };
    let router = api::router::build(app_state);

    let listener = tokio::net::TcpListener::bind("0.0.0.0:3000").await?;
    tracing::info!("API server listening on :3000");

    tokio::select! {
        _ = dispatch_engine.run() => {
            tracing::warn!("Dispatch engine stopped");
        }
        _ = axum::serve(listener, router) => {
            tracing::warn!("HTTP server stopped");
        }
        _ = tokio::signal::ctrl_c() => {
            tracing::info!("Received SIGINT, shutting down...");
        }
    }

    tracing::info!("Shutdown complete");
    Ok(())
}
