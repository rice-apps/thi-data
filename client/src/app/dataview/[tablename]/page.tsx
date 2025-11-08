import React from "react";

type Props = {
  params: { tablename: string }; 
};

export default async function DataViewPage({ params }: Props) {
  const tableName = params.tablename;

  let data: any;
  let error: string | null = null;

  try {
    data = await getTableData(tableName);
  } catch (err: any) {
    error = err?.message ?? String(err);
  }

  if (error) {
    return (
      <main style={{ padding: 24 }}>
        <h1>Error loading table <code>{tableName}</code></h1>
        <pre>{error}</pre>
      </main>
    );
  }

  return (
    <main style={{ padding: 24 }}>
      <h1>
        The table is: <b>{tableName}</b>
      </h1>
      <pre style={{ whiteSpace: "pre-wrap" }}>{JSON.stringify(data, null, 2)}</pre>
    </main>
  );
}

async function getTableData(tableName: string): Promise<any> {
  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  const url = `${backendUrl.replace(/\/$/, "")}/api/${encodeURIComponent(tableName)}`;

  const resp = await fetch(url, {
    cache: "no-store",
  });

  if (!resp.ok) {
        const bodyText = await resp.text().catch(() => "");
    throw new Error(`Fetch failed (${resp.status} ${resp.statusText})${bodyText ? `: ${bodyText}` : ""}`);
  }

  return resp.json();
}
