import React from "react";
import { loginResult } from "@/utils/checklogin";
import { redirect } from "next/navigation";
import { getAPI } from "@/utils/adapter";
import SearchForm from "./SearchForm"; 
import Pagination from "./pagination";
import type { ReactNode } from "react";

type PageProps = {
  params: Promise<{ tablename: string }>;
  searchParams: Promise<{ [key: string]: string | string[] | undefined, page?: string, limit?: string}>;
};

type TableRow = { id: string | number } & Record<string, unknown>;

export default async function DataViewPage(props: PageProps) {
  const params = await props.params;
  const searchParams = await props.searchParams;

  const { tablename } = params;
  const column = typeof searchParams.column === 'string' ? searchParams.column : undefined;
  const search = typeof searchParams.search === 'string' ? searchParams.search : undefined;

  const user = await loginResult();
  if (!user) redirect("/login");

  const page = Number(searchParams.page) || 1;
  const limit = Number(searchParams.limit) || 10;
  
  const skip = (page - 1) * limit;

  // Prepare the query object
  const paginationParams = { skip, limit };

  let response;

  try {
    if (column && search) {
      // Pass path as arg 1, pagination as arg 2
      response = await getAPI(
        `${tablename}/search/${column}/${encodeURIComponent(search)}`, 
        paginationParams
      );
    } else {
      // Pass path as arg 1, pagination as arg 2
      response = await getAPI(tablename, paginationParams);
    }
  } catch (err: any) {
    // error = err?.message ?? String(err);
  }

  // Handle the new response shape { data: [...], total: 123 }
  // We use optional chaining in case error happened and response is undefined
  const data = response?.data || []; 
  const totalItems = response?.total || 0;
  let error: string | null = null;


  if (error) {
    return (
      <main className="p-4 text-red-600">
        <strong>Error:</strong> {error}
      </main>
    );
  }
  const hasData = Array.isArray(data) && data.length > 0;
  let headers: string[] = [];

  if (Array.isArray(data) && data.length > 0) {
     headers = Object.keys(data[0]).filter((key) => key !== "id");
  } else {
    try {
      // We fetch with limit=1 for speed
      const sampleResponse = await getAPI(tablename, { limit: 1 });
      
      const sampleRows = sampleResponse?.data || [];
      
      if (Array.isArray(sampleRows) && sampleRows.length > 0) {
          headers = Object.keys(sampleRows[0]).filter((key) => key !== "id");
      }
     } catch (e) {
       console.warn("Could not fetch sample data for headers");
     }
  }

  const totalPages = Math.ceil(totalItems / limit);

  return (
    <div className="flex flex-col h-screen bg-gray-50 p-4 overflow-hidden">
      
      <div className="flex justify-between items-center mb-4 bg-white p-3 rounded shadow-sm">
        <h1 className="text-lg font-bold capitalize text-gray-700">{tablename}</h1>

        <SearchForm 
          tablename={tablename}
          headers={headers}
          initialColumn={column}
          initialSearch={search}
        />
      </div>

      <div className="flex-1 overflow-auto rounded bg-white shadow-sm">
        {!hasData ? (
          <div className="p-4 text-sm text-gray-500 italic">No records found.</div>
        ) : (
          <table className="w-full text-left">
            <thead className="bg-gray-100 text-xs uppercase text-gray-600 sticky top-0 z-10 shadow-sm">
              <tr>
                {headers.map((header) => (
                  <th key={header} className="py-2 px-3 font-semibold">
                    {header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="text-xs text-gray-700 divide-y">
              {data.map((row) => (
                <tr key={row.id} className="hover:bg-blue-50 transition-colors">
                  {headers.map((colName) => {
                    const cellValue = row[colName];
                    return (
                      <td key={`${row.id}-${colName}`} className="py-1 px-3 whitespace-nowrap border-r last:border-r-0 border-gray-100">
                         {cellValue ? String(cellValue) : <span className="text-gray-300">-</span>}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      
      <div className="mt-5 flex w-full justify-center">
        <Pagination totalPages={totalPages} />
      </div>
    </div>
  );
}
