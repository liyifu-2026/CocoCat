export class ApiError extends Error {
  status: number
  body: unknown
  constructor(message: string, status: number, body: unknown) {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.body = body
  }
}

const BASE = "/api"

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers ?? undefined)
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json")
  }
  const token = localStorage.getItem("cococat_token")
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }
  const res = await fetch(`${BASE}${path}`, {
    headers, credentials: "include", ...init,
  })
  if (res.status === 401) {
    localStorage.removeItem("cococat_token")
    window.location.href = "/login"
    throw new ApiError("Unauthorized", 401, null)
  }
  if (!res.ok) {
    const body = await res.json().catch(() => null)
    throw new ApiError(
      (body as { error?: string; detail?: string } | null)?.error ??
      (body as { detail?: string } | null)?.detail ??
      `Request failed: ${res.status}`,
      res.status, body,
    )
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body: unknown) => request<T>(path, { method: "POST", body: JSON.stringify(body) }),
  put: <T>(path: string, body: unknown) => request<T>(path, { method: "PUT", body: JSON.stringify(body) }),
  patch: <T>(path: string, body: unknown) => request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
}
