
// Returns result of /api/{path} from backend.
export async function getAPI(path: string, queryParams?: Record<string, string | number>) {
  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  
  // 1. Remove strict encoding on the full path so slashes in "search/col/val" persist.
  // We assume 'path' is clean or already encoded by the caller for specific segments.
  let urlStr = `${backendUrl.replace(/\/$/, "")}/api/${path}`;

  // 2. Append Query Parameters cleanly using URLSearchParams
  if (queryParams) {
    const params = new URLSearchParams();
    Object.entries(queryParams).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        params.append(key, String(value));
      }
    });
    // Append to URL (handles the ? automatically)
    urlStr += `?${params.toString()}`;
  }

  const resp = await fetch(urlStr, {
    cache: "no-store",
  });

  if (!resp.ok) {
    const bodyText = await resp.text().catch(() => "");
    throw new Error(`Fetch failed (${resp.status} ${resp.statusText})${bodyText ? `: ${bodyText}` : ""}`);
  }

  return resp.json();
}