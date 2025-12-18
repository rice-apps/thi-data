import React from 'react';
import Link from 'next/link';
import { loginResult } from '@/utils/checklogin';
import { redirect } from 'next/navigation';
import ApiService from '@/services/api';
import { TableRow, PaginatedResponse } from '@/services/types';
import DataTable from './DataTable';
import SearchForm from './SearchForm';
import Pagination from './pagination';

type PageProps = {
  params: Promise<{ tablename: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
};

export default async function DataViewPage(props: PageProps) {
  const params = await props.params;
  const searchParams = await props.searchParams;
  const { tablename } = params;

  // 1. Check Authentication
  const user = await loginResult();
  if (!user) {
    redirect('/login');
  }

  // 2. Parse Query Parameters
  const page = Number(searchParams.page) || 1;
  const limit = Number(searchParams.limit) || 10;
  const search =
    typeof searchParams.search === 'string' ? searchParams.search : undefined;
  const column =
    typeof searchParams.column === 'string' ? searchParams.column : undefined;
  const skip = (page - 1) * limit;

  // 3. Fetch Data & Schema
  let data: TableRow[] = [];
  let columns: string[] = [];
  let totalItems = 0;
  let error: string | null = null;

  try {
    const paginationParams = { skip, limit };
    let dataResponse: PaginatedResponse<TableRow>;

    // Fetch Table Data
    if (column && search) {
      dataResponse = await ApiService.searchTableData(
        tablename,
        column,
        search,
        paginationParams
      );
    } else {
      dataResponse = await ApiService.getTableData(tablename, paginationParams);
    }

    // Handle response format
    data = dataResponse?.data || [];
    totalItems = dataResponse?.total || 0;

    // Fetch Schema (Columns)
    try {
      const schemaResponse = await ApiService.getTableSchema(tablename);
      columns = schemaResponse?.columns || [];
    } catch {
      // Fallback: infer columns from first row of data if schema fails
      if (data.length > 0) {
        columns = Object.keys(data[0]).filter((k) => k !== 'id');
      }
    }
  } catch (err: unknown) {
    if (err instanceof Error) {
      error = err.message;
    } else {
      error = 'Failed to load data';
    }
  }

  const totalPages = Math.ceil(totalItems / limit);

  // 4. Render Error State
  if (error) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50 p-8">
        <div className="max-w-7xl mx-auto bg-white rounded-2xl shadow-sm border border-red-200 p-8">
          <h2 className="text-xl font-semibold text-red-600 mb-2">
            Error loading table
          </h2>
          <pre className="text-sm text-slate-600 bg-slate-50 p-4 rounded-lg overflow-x-auto">
            {error}
          </pre>
          <Link
            href="/homescreen"
            className="mt-4 inline-block text-blue-600 hover:underline"
          >
            Return to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  // Generate a key to force DataTable to re-mount when data context changes
  const dataTableKey = `${tablename}-${page}-${search || 'all'}-${column || 'none'}`;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50">
      {/* Top Navigation Bar */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col md:flex-row md:items-center gap-4 justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/homescreen"
              className="p-2 -ml-2 text-slate-500 hover:text-[#1c66bb] hover:bg-slate-100 rounded-lg transition-all duration-200"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </Link>
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wider">
                Table
              </p>
              <h1 className="text-xl font-semibold text-slate-800 capitalize">
                {tablename}
              </h1>
            </div>
          </div>

          <div className="flex-1 max-w-xl md:ml-4">
            <SearchForm
              tablename={tablename}
              headers={columns}
              initialColumn={column}
              initialSearch={search}
            />
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <DataTable
          key={dataTableKey}
          tablename={tablename}
          initialData={data}
          columns={columns}
        />

        <div className="mt-6 flex justify-center">
          <Pagination totalPages={totalPages} />
        </div>
      </main>
    </div>
  );
}
