import React from 'react';
import Link from 'next/link';
import { loginResult } from '@/utils/checklogin';
import { redirect } from 'next/navigation';
import { ServiceFactory } from '@/services';
import type { TableRow } from '@/types';
import DataTable from './DataTable';

type PageProps = {
  params: Promise<{ tablename: string }>;
};

export default async function DataViewPage(props: PageProps) {
  const params = await props.params;
  const { tablename } = params;

  const user = await loginResult();
  if (!user) {
    redirect('/login');
  }

  const dataService = ServiceFactory.getDataService();

  let data: TableRow[] = [];
  let columns: string[] = [];
  let error: string | null = null;

  try {
    const [dataResponse, schemaResponse] = await Promise.all([
      dataService.getTableData(tablename, { skip: 0, limit: 50 }),
      dataService.getTableSchema(tablename).catch(() => null),
    ]);

    data = dataResponse?.data || [];
    columns = schemaResponse?.columns || [];

    if (columns.length === 0 && data.length > 0) {
      columns = Object.keys(data[0]);
    }
    columns = columns.filter((k) => !k.startsWith('_'));
  } catch (err: unknown) {
    if (err instanceof Error) {
      error = err.message;
    } else {
      error = 'Failed to load data';
    }
  }

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

  return (
    <DataTable tablename={tablename} initialData={data} columns={columns} />
  );
}
