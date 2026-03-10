'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useServices } from '@/services';
import { useProcessing } from '@/components/ProcessingProvider';
import { COLORS, BRANDING } from '@/constants';
import { Spinner } from '@/components/Spinner';
import { SearchInput } from '@/components/SearchInput';
import { formatValue } from '@/utils/formatters';
import type { TableMetadata } from '@/types';
import { signOutAction } from '../auth/actions';

export default function HomeScreen() {
  const router = useRouter();
  const { dataService } = useServices();
  const { lastSuccessTimestamp } = useProcessing();
  const [tables, setTables] = useState<TableMetadata[]>([]);
  const [search, setSearch] = useState('');
  const [hoveredTable, setHoveredTable] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [fabHovered, setFabHovered] = useState(false);

  const fetchTables = useCallback(() => {
    dataService
      .getTablesWithMetadata()
      .then((data) => setTables(data.tables))
      .catch((error) => console.error(error))
      .finally(() => setLoading(false));
  }, [dataService]);

  useEffect(() => {
    fetchTables();
  }, [fetchTables, lastSuccessTimestamp]);

  const filteredTables = tables.filter((table) =>
    table?.name?.toLowerCase().includes(search.toLowerCase())
  );

  const handleSignOut = async () => {
    await signOutAction();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50">
      <header className="bg-white/80 backdrop-blur-sm border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div
              className="w-10 h-10 rounded-xl flex items-center justify-center"
              style={{
                background: `linear-gradient(to bottom right, ${COLORS.PRIMARY}, ${COLORS.PRIMARY_DARK})`,
              }}
            >
              <span className="text-white font-bold text-lg">T</span>
            </div>
            <div>
              <h1 className="text-xl font-semibold text-slate-800">
                {BRANDING.COMPANY_NAME}
              </h1>
              <p className="text-xs text-slate-500">{BRANDING.APP_SUBTITLE}</p>
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

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="mb-8">
          <SearchInput
            value={search}
            onChange={setSearch}
            placeholder="Search tables..."
            className="max-w-xl mx-auto"
          />
        </div>

        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="grid grid-cols-12 gap-4 px-6 py-4 bg-slate-50 border-b border-slate-200 text-sm font-semibold text-slate-600">
            <div className="col-span-4">Table Name</div>
            <div className="col-span-2">Uploaded By</div>
            <div className="col-span-2">Date Uploaded</div>
            <div className="col-span-2">Date Modified</div>
            <div className="col-span-2 text-right">Size</div>
          </div>

          {loading ? (
            <div className="px-6 py-12 text-center text-slate-500">
              <Spinner className="mx-auto mb-3" />
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
                      ? `bg-[#cfeff8] border-l-4 border-[${COLORS.PRIMARY}]`
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

      {/* Floating Action Button */}
      <button
        onClick={() => router.push('/data_upload')}
        onMouseEnter={() => setFabHovered(true)}
        onMouseLeave={() => setFabHovered(false)}
        className={`fixed bottom-8 right-8 h-14 text-white font-medium rounded-full shadow-lg hover:shadow-xl hover:shadow-blue-500/25 transition-all duration-300 flex items-center overflow-hidden ${
          fabHovered
            ? 'w-40 pl-4 pr-5 justify-start gap-2'
            : 'w-14 justify-center'
        }`}
        style={{
          background: `linear-gradient(to right, ${COLORS.PRIMARY}, ${COLORS.PRIMARY_DARK})`,
        }}
      >
        <svg
          className="w-6 h-6 flex-shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 4v16m8-8H4"
          />
        </svg>
        <span
          className={`whitespace-nowrap transition-opacity duration-300 ${
            fabHovered ? 'opacity-100' : 'opacity-0 w-0'
          }`}
        >
          Upload File
        </span>
      </button>
    </div>
  );
}
