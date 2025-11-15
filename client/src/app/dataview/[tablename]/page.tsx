import React from "react";
import { loginResult } from "@/utils/supabase/isloggedin";
import { redirect } from 'next/navigation';

type Props = {
  params: { tablename: string };
};

export default async function DataViewPage({ params }: Props) {
  const { tablename } = await params;

  // check if logged in
  const user = await loginResult(); 
  if (!user){
    redirect('/login'); 
  }

  let data: any;
  let error: string | null = null;

  try {
    data = await getTableData(tablename);
  } catch (err: any) {
    error = err?.message ?? String(err);
  }

  if (error) {
    return (
      <main style={{ padding: 24 }}>
        <h1>Error loading table <code>{tablename}</code></h1>
        <pre>{error}</pre>
      </main>
    );
  }

  // Avoid displaying or indexing into empty table
  if (data.length == 0) {
    return (
      <h2> <b>No content!!!!!!!! </b></h2>
    )
  }

  // remove the id field, avoid showing it in dataview.
  const content = data.map(({ id, ...rest }) => rest);

  const headers = Object.keys(content[0]);

  const rows = content.map(key => Object.values(key));
  console.log(`Rows: ${rows}`);
  return (
    <div className="flex flex-col items-center min-h-screen bg-gray-50 p-8">
      <h1 className="text-center text-3xl py-5">{tablename}</h1>
      <table>
        <thead>
          <tr>
            {headers.map(header => <th key={header} className="text-center px-10">{header}</th>)}
          </tr>
        </thead>
        <tbody className="text-sm">
          {rows.map((row: any, index: any) => (
            <tr key={index}>
              {row.map((cell: any, index: any) => <td key={index} className={`text-center ${cell ? "" : "text-gray-400 italic"}`}>{cell ? cell : "null"}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}


// Pull data from the backend by the tableName
async function getTableData(rawTableName: string): Promise<any> {
  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  const url = `${backendUrl.replace(/\/$/, "")}/api/${encodeURIComponent(rawTableName)}`;

  const resp = await fetch(url, {
    cache: "no-store",
  });

  if (!resp.ok) {
    const bodyText = await resp.text().catch(() => "");
    throw new Error(`Fetch failed (${resp.status} ${resp.statusText})${bodyText ? `: ${bodyText}` : ""}`);
  }

  return resp.json();
}
