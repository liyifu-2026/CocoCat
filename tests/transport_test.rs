use cococat::transport::{JsonRpcRequest, JsonRpcResponse, JsonRpcError};

#[test]
fn test_request_creation() {
    let req = JsonRpcRequest::new("ping", None, 1);
    assert_eq!(req.method, "ping");
    assert_eq!(req.id, 1);
    assert_eq!(req.jsonrpc, "2.0");
}

#[test]
fn test_request_with_params() {
    let params = serde_json::json!({"key": "value"});
    let req = JsonRpcRequest::new("echo", Some(params.clone()), 2);
    assert_eq!(req.params, Some(params));
}

#[test]
fn test_response_with_result() {
    let resp = JsonRpcResponse {
        jsonrpc: "2.0".to_string(),
        result: Some(serde_json::json!({"pong": true})),
        error: None,
        id: Some(1),
    };
    assert!(resp.result.is_some());
    assert!(resp.error.is_none());
}

#[test]
fn test_response_with_error() {
    let resp = JsonRpcResponse {
        jsonrpc: "2.0".to_string(),
        result: None,
        error: Some(JsonRpcError { code: -32603, message: "test error".to_string() }),
        id: Some(1),
    };
    assert!(resp.result.is_none());
    assert!(resp.error.is_some());
}
