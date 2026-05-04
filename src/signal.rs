use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;

pub fn setup() -> Arc<AtomicBool> {
    Arc::new(AtomicBool::new(true))
}

pub fn is_shutdown(flag: &AtomicBool) -> bool {
    !flag.load(Ordering::Relaxed)
}
