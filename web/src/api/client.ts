export async function apiRequest<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || `请求失败 (${response.status})`);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function uploadDocument(file: File) {
  const body = new FormData();
  body.append("file", file);
  const response = await fetch("/api/documents", { method: "POST", credentials: "include", body });
  if (!response.ok) throw new Error((await response.json()).detail || "资料上传失败");
  return response.json();
}
