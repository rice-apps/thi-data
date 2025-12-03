import React from "react";
import Link from "next/link";
import { loginResult } from "@/utils/supabase/isloggedin";
import { redirect } from "next/navigation";
import DataTable from "./DataTable";

type Props = {
  params: Promise<{ tablename: string }>;
};

export default async function DataViewPage({ params }: Props) {
  const { tablename } = await params;

  const user = await loginResult();
  if (!user) {
    redirect("/login");
  }

  let data: any[] = [];
  let columns: string[] = [];
  let error: string | null = null;

  try {
    // Fetch both data and schema in parallel
    const [dataResult, schemaResult] = await Promise.all([
      getTableData(tablename),
      getTableSchema(tablename),
    ]);
    data = dataResult;
    columns = schemaResult;
  } catch (err: any) {
    error = err?.message ?? String(err);
  }

  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50">
        <Header tablename={tablename} />
        <main className="max-w-7xl mx-auto px-6 py-8">
          <div className="bg-white rounded-2xl shadow-sm border border-red-200 p-8">
            <h2 className="text-xl font-semibold text-red-600 mb-2">Error loading table</h2>
            <pre className="text-sm text-slate-600 bg-slate-50 p-4 rounded-lg overflow-x-auto">{error}</pre>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50">
      <Header tablename={tablename} />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <DataTable 
          tablename={tablename} 
          initialData={data} 
          columns={columns} 
        />
      </main>
    </div>
  );
}

function Header({ tablename }: { tablename: string }) {
  return (
    <header className="bg-white/80 backdrop-blur-sm border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center gap-4">
        <Link
          href="/homescreen"
          className="p-2 -ml-2 text-slate-500 hover:text-[#1c66bb] hover:bg-slate-100 rounded-lg transition-all duration-200"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Link>
        <div>
          <p className="text-xs text-slate-500 uppercase tracking-wider">Table</p>
          <h1 className="text-xl font-semibold text-slate-800">{tablename}</h1>
        </div>
      </div>
    </header>
  );
}

async function getTableData(rawTableName: string): Promise<any[]> {
  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  const url = `${backendUrl.replace(/\/$/, "")}/api/${encodeURIComponent(rawTableName)}`;

  const resp = await fetch(url, { cache: "no-store" });

  if (!resp.ok) {
    const bodyText = await resp.text().catch(() => "");
    throw new Error(`Fetch failed (${resp.status} ${resp.statusText})${bodyText ? `: ${bodyText}` : ""}`);
  }

  return resp.json();
}

async function getTableSchema(rawTableName: string): Promise<string[]> {
  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  const url = `${backendUrl.replace(/\/$/, "")}/api/schema/${encodeURIComponent(rawTableName)}`;

  const resp = await fetch(url, { cache: "no-store" });

  if (!resp.ok) {
    const bodyText = await resp.text().catch(() => "");
    throw new Error(`Schema fetch failed (${resp.status} ${resp.statusText})${bodyText ? `: ${bodyText}` : ""}`);
  }

  const data = await resp.json();
  return data.columns;
}
