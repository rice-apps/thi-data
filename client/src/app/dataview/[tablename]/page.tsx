import React from "react";
import Link from "next/link";
import { loginResult } from "@/utils/supabase/isloggedin";
import { redirect } from "next/navigation";

type Props = {
  params: Promise<{ tablename: string }>;
};

export default async function DataViewPage({ params }: Props) {
  const { tablename } = await params;

  const user = await loginResult();
  if (!user) {
    redirect("/login");
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

  if (!data || data.length === 0) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50">
        <Header tablename={tablename} />
        <main className="max-w-7xl mx-auto px-6 py-8">
          <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-12 text-center">
            <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-slate-100 flex items-center justify-center">
              <svg className="w-8 h-8 text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4" />
              </svg>
            </div>
            <h2 className="text-xl font-semibold text-slate-700">No Data</h2>
            <p className="text-slate-500 mt-1">This table is empty.</p>
          </div>
        </main>
      </div>
    );
  }

  const content = data.map(({ id, ...rest }: any) => rest);
  const headers = Object.keys(content[0]);
  const rows = content.map((item: any) => Object.values(item));

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50">
      <Header tablename={tablename} />
      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  {headers.map((header) => (
                    <th
                      key={header}
                      className="px-6 py-4 text-left text-sm font-semibold text-slate-600 whitespace-nowrap"
                    >
                      {header}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {rows.map((row: any[], rowIndex: number) => (
                  <tr key={rowIndex} className="hover:bg-slate-50 transition-colors">
                    {row.map((cell: any, cellIndex: number) => (
                      <td
                        key={cellIndex}
                        className={`px-6 py-4 text-sm whitespace-nowrap ${
                          cell ? "text-slate-700" : "text-slate-400 italic"
                        }`}
                      >
                        {cell ?? "null"}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
        <p className="text-center text-sm text-slate-500 mt-4">
          {rows.length} row{rows.length !== 1 ? "s" : ""} • {headers.length} column{headers.length !== 1 ? "s" : ""}
        </p>
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

async function getTableData(rawTableName: string): Promise<any> {
  const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";
  const url = `${backendUrl.replace(/\/$/, "")}/api/${encodeURIComponent(rawTableName)}`;

  const resp = await fetch(url, { cache: "no-store" });

  if (!resp.ok) {
    const bodyText = await resp.text().catch(() => "");
    throw new Error(`Fetch failed (${resp.status} ${resp.statusText})${bodyText ? `: ${bodyText}` : ""}`);
  }

  return resp.json();
}
