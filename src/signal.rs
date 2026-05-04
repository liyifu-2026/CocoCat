use std::sync::atomic::AtomicBool;
use std::sync::Arc;

pub fn setup() -> Arc<AtomicBool> {
    Arc::new(AtomicBool::new(false))
}
