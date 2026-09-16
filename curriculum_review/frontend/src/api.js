export async function api(path, options = {}) {
  const body = options.body;
  const response = await fetch("/api" + path, {
    ...options,
    credentials: "same-origin",
    headers:
      body && !(body instanceof FormData)
        ? { "Content-Type": "application/json", ...options.headers }
        : options.headers,
    body: body && !(body instanceof FormData) ? JSON.stringify(body) : body,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok)
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : "Could not complete this action. Check the fields and try again.",
    );
  return data;
}
