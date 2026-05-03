/**
 * Shared API client for RR Command Center frontend.
 *
 * Why this exists
 * ---------------
 * Before Phase 0, every page reinvented `const fetcher = (url: string) =>
 * fetch(url).then(r => r.json())`. That meant: relative URLs only (broken in
 * production where API and UI live on different hosts), no auth header
 * injection, no error handling, no shape on errors. This file fixes all four.
 *
 * Usage
 * -----
 *   import { api, apiFetcher } from "@/lib/api";
 *
 *   // SWR
 *   const { data, error } = useSWR<EntityOut[]>("/api/entities", apiFetcher);
 *
 *   // Direct calls
 *   const me = await api.get<MeOut>("/api/me");
 *   await api.patch("/api/tasks/123", { status: "done" });
 *
 *   // SSE (with proper cleanup)
 *   const stream = api.stream("/api/feed/stream", { onMessage: (item) => ... });
 *   // later: stream.close();
 *
 * Auth
 * ----
 * When MSAL is wired up (Phase 1B), `setAuthTokenProvider` lets you inject a
 * token getter. Until then, all calls are unauthenticated and the backend's
 * dev-bypass kicks in.
 */

// ─── config ──────────────────────────────────────────────────────────────────

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

let _tokenProvider: (() => Promise<string | null>) | null = null;

/**
 * Register an async function that returns a Bearer token (or null).
 * Call this once after MSAL initializes.
 */
export function setAuthTokenProvider(fn: (() => Promise<string | null>) | null) {
  _tokenProvider = fn;
}

async function _authHeader(): Promise<Record<string, string>> {
  if (!_tokenProvider) return {};
  try {
    const token = await _tokenProvider();
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

// ─── error type ──────────────────────────────────────────────────────────────

export class ApiError extends Error {
  status: number;
  detail: string;
  url: string;

  constructor(status: number, detail: string, url: string) {
    super(`[${status}] ${detail}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.url = url;
  }

  /** True if the user should be redirected to sign in. */
  get isAuth() {
    return this.status === 401 || this.status === 403;
  }
}

// ─── url helper ──────────────────────────────────────────────────────────────

function _url(path: string): string {
  if (/^https?:\/\//i.test(path)) return path;
  return `${API_BASE_URL}${path.startsWith("/") ? "" : "/"}${path}`;
}

// ─── core request ────────────────────────────────────────────────────────────

interface RequestOpts {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

async function _request<T>(path: string, opts: RequestOpts = {}): Promise<T> {
  const url = _url(path);
  const auth = await _authHeader();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...auth,
    ...(opts.headers || {}),
  };

  let response: Response;
  try {
    response = await fetch(url, {
      method: opts.method ?? "GET",
      headers,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
      signal: opts.signal,
      credentials: "include",
    });
  } catch (e: any) {
    throw new ApiError(0, `Network error: ${e?.message || "unreachable"}`, url);
  }

  if (!response.ok) {
    let detail = response.statusText || "Request failed";
    try {
      const body = await response.json();
      detail = body.detail || body.error || detail;
    } catch {
      // body wasn't JSON; fall through with statusText
    }
    throw new ApiError(response.status, detail, url);
  }

  // 204 No Content
  if (response.status === 204) return undefined as T;

  return response.json() as Promise<T>;
}

// ─── public api ──────────────────────────────────────────────────────────────

export const api = {
  get: <T = unknown>(path: string, opts?: Omit<RequestOpts, "method" | "body">) =>
    _request<T>(path, { ...opts, method: "GET" }),

  post: <T = unknown>(path: string, body?: unknown, opts?: Omit<RequestOpts, "method" | "body">) =>
    _request<T>(path, { ...opts, method: "POST", body }),

  patch: <T = unknown>(path: string, body?: unknown, opts?: Omit<RequestOpts, "method" | "body">) =>
    _request<T>(path, { ...opts, method: "PATCH", body }),

  put: <T = unknown>(path: string, body?: unknown, opts?: Omit<RequestOpts, "method" | "body">) =>
    _request<T>(path, { ...opts, method: "PUT", body }),

  delete: <T = unknown>(path: string, opts?: Omit<RequestOpts, "method" | "body">) =>
    _request<T>(path, { ...opts, method: "DELETE" }),

  /**
   * Open an SSE stream. Returns a handle with .close() — ALWAYS call it on
   * component unmount. Auto-reconnects on transient network drops; surfaces
   * fatal errors via onError.
   */
  stream(
    path: string,
    {
      onMessage,
      onError,
      onOpen,
    }: {
      onMessage: (data: any) => void;
      onError?: (e: Event) => void;
      onOpen?: () => void;
    },
  ) {
    const url = _url(path);
    let es: EventSource | null = new EventSource(url, { withCredentials: true });
    let closed = false;

    es.onopen = () => onOpen?.();
    es.onmessage = (e) => {
      try {
        onMessage(JSON.parse(e.data));
      } catch (parseErr) {
        // malformed payload; let the consumer decide
        onError?.(new MessageEvent("error", { data: parseErr }));
      }
    };
    es.onerror = (e) => {
      if (closed) return;
      onError?.(e);
    };

    return {
      close() {
        if (closed) return;
        closed = true;
        es?.close();
        es = null;
      },
    };
  },
};

/**
 * SWR-compatible fetcher. Pass as the second arg to useSWR:
 *   const { data } = useSWR<EntityOut[]>("/api/entities", apiFetcher);
 */
export const apiFetcher = <T = unknown>(path: string) => api.get<T>(path);

export { API_BASE_URL };
