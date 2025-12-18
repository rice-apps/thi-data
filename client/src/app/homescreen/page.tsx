'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useServices } from '@/providers/ServiceProvider';
import { TableMetadata } from '@/services/types';

export default function HomeScreen() {
  const router = useRouter();
  const { authService, dataService } = useServices();
  const [tables, setTables] = useState<TableMetadata[]>([]);
  const [search, setSearch] = useState('');
  const [hoveredTable, setHoveredTable] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dataService
      .getTablesWithMetadata()
      .then((data) => {
        setTables(data.tables);
      })
      .catch((error) => console.error(error))
      .finally(() => setLoading(false));
  }, [dataService]);

  const filteredTables = tables.filter((table) =>
    table?.name?.toLowerCase().includes(search.toLowerCase())
  );

  const handleSignOut = async () => {
    await authService.signOut();
    router.push('/login');
  };

  const formatValue = (value: string | null, fallback: string = '—') => {
    return value || fallback;
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-[#1c66bb] to-[#0d4a8f] flex items-center justify-center">
              <span className="text-white font-bold text-lg">T</span>
            </div>
            <div>
              <h1 className="text-xl font-semibold text-slate-800">
                Texas Hearing Institute
              </h1>
              <p className="text-xs text-slate-500">Data Warehouse</p>
            </div>
          </div>
          <button
            onClick={handleSignOut}
            className="px-4 py-2 text-sm font-medium text-red-600 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 hover:border-red-300 transition-all duration-200"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Search Bar */}
        <div className="mb-8">
          <div className="relative max-w-xl mx-auto">
            <svg
              className="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-slate-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
              />
            </svg>
            <input
              type="text"
              placeholder="Search tables..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-12 pr-4 py-3 text-slate-700 bg-white border border-slate-200 rounded-2xl shadow-sm focus:outline-none focus:ring-2 focus:ring-[#1c66bb]/30 focus:border-[#1c66bb] transition-all duration-200"
            />
          </div>
        </div>

        {/* Table List */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          {/* Table Header */}
          <div className="grid grid-cols-12 gap-4 px-6 py-4 bg-slate-50 border-b border-slate-200 text-sm font-semibold text-slate-600">
            <div className="col-span-4">Table Name</div>
            <div className="col-span-2">Uploaded By</div>
            <div className="col-span-2">Date Uploaded</div>
            <div className="col-span-2">Date Modified</div>
            <div className="col-span-2 text-right">Size</div>
          </div>

          {/* Table Rows */}
          {loading ? (
            <div className="px-6 py-12 text-center text-slate-500">
              <div className="inline-block w-6 h-6 border-2 border-[#1c66bb] border-t-transparent rounded-full animate-spin mb-3"></div>
              <p>Loading tables...</p>
            </div>
          ) : filteredTables.length === 0 ? (
            <div className="px-6 py-12 text-center text-slate-500">
              <p>No tables found</p>
            </div>
          ) : (
            <div className="divide-y divide-slate-100">
              {filteredTables.map((table) => (
                <div
                  key={table.name}
                  onClick={() => router.push(`/dataview/${table.name}`)}
                  onMouseEnter={() => setHoveredTable(table.name)}
                  onMouseLeave={() => setHoveredTable(null)}
                  className={`grid grid-cols-12 gap-4 px-6 py-4 cursor-pointer transition-all duration-200 ${
                    hoveredTable === table.name
                      ? 'bg-[#cfeff8] border-l-4 border-[#1c66bb]'
                      : 'hover:bg-slate-50 border-l-4 border-transparent'
                  }`}
                >
                  <div className="col-span-4 font-medium text-slate-800">
                    {table.name}
                  </div>
                  <div
                    className={`col-span-2 ${table.uploadedBy ? 'text-slate-600' : 'text-slate-400 italic'}`}
                  >
                    {formatValue(table.uploadedBy)}
                  </div>
                  <div
                    className={`col-span-2 ${table.dateUploaded ? 'text-slate-600' : 'text-slate-400 italic'}`}
                  >
                    {formatValue(table.dateUploaded)}
                  </div>
                  <div
                    className={`col-span-2 ${table.dateModified ? 'text-slate-600' : 'text-slate-400 italic'}`}
                  >
                    {formatValue(table.dateModified)}
                  </div>
                  <div
                    className={`col-span-2 text-right ${table.size ? 'text-slate-600' : 'text-slate-400 italic'}`}
                  >
                    <span className="inline-flex items-center gap-1">
                      {table.size && (
                        <svg
                          className="w-4 h-4 text-slate-400"
                          fill="none"
                          stroke="currentColor"
                          viewBox="0 0 24 24"
                        >
                          <path
                            strokeLinecap="round"
                            strokeLinejoin="round"
                            strokeWidth={2}
                            d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4"
                          />
                        </svg>
                      )}
                      {formatValue(table.size)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
