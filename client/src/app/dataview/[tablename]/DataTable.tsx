'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { TableRow } from '@/services/types';
import ApiService from '@/services/api';
import { getCurrentUserName } from '@/utils/supabase/client';

interface DataTableProps {
  tablename: string;
  initialData: TableRow[];
  columns: string[];
}

const PAGE_SIZE = 50;

export default function DataTable({
  tablename,
  initialData,
  columns,
}: DataTableProps) {
  // Data State
  const [data, setData] = useState<TableRow[]>(initialData);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(false);

  // Search State
  const [search, setSearch] = useState('');
  const [selectedColumn, setSelectedColumn] = useState(columns[0] || 'id');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  // UI State
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [selectedRow, setSelectedRow] = useState<TableRow | null>(null);
  const [formData, setFormData] = useState<TableRow>({});
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [currentUser, setCurrentUser] = useState<string>('');

  useEffect(() => {
    getCurrentUserName().then(setCurrentUser);
  }, []);

  const observerTarget = useRef<HTMLDivElement>(null);
  const isFirstRender = useRef(true);

  // Handle Debounce
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(search);
    }, 150); // Reduced from 300ms

    return () => clearTimeout(handler);
  }, [search]);

  // Reset and Fetch on Search/Column Change
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    const fetchFirstPage = async () => {
      setInitialLoading(true);
      setPage(1);
      try {
        const paginationParams = { skip: 0, limit: PAGE_SIZE };
        let response;

        if (debouncedSearch) {
          response = await ApiService.searchTableData(
            tablename,
            selectedColumn,
            debouncedSearch,
            paginationParams
          );
        } else {
          response = await ApiService.getTableData(tablename, paginationParams);
        }

        const newData = response.data || [];
        setData(newData);
        setHasMore(newData.length >= PAGE_SIZE);
      } catch {
        showError('Failed to search data');
      } finally {
        setInitialLoading(false);
      }
    };

    fetchFirstPage();
  }, [debouncedSearch, selectedColumn, tablename]);

  // Infinite Scroll: Fetch Next Page
  const loadMore = useCallback(async () => {
    if (loading || !hasMore) return;

    setLoading(true);
    try {
      const skip = page * PAGE_SIZE;
      const paginationParams = { skip, limit: PAGE_SIZE };
      let response;

      if (debouncedSearch) {
        response = await ApiService.searchTableData(
          tablename,
          selectedColumn,
          debouncedSearch,
          paginationParams
        );
      } else {
        response = await ApiService.getTableData(tablename, paginationParams);
      }

      const newData = response.data || [];
      if (newData.length < PAGE_SIZE) {
        setHasMore(false);
      }

      setData((prev) => [...prev, ...newData]);
      setPage((prev) => prev + 1);
    } catch {
      showError('Failed to load more data');
    } finally {
      setLoading(false);
    }
  }, [page, loading, hasMore, debouncedSearch, selectedColumn, tablename]);

  // Intersection Observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        if (
          entries[0].isIntersecting &&
          hasMore &&
          !loading &&
          !initialLoading
        ) {
          loadMore();
        }
      },
      { threshold: 1.0 }
    );

    const element = observerTarget.current;
    if (element) {
      observer.observe(element);
    }

    return () => {
      if (element) {
        observer.unobserve(element);
      }
    };
  }, [loadMore, hasMore, loading, initialLoading]);

  // Helpers
  const showSuccess = (msg: string) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
  };

  const showError = (msg: string) => {
    setError(msg);
    setTimeout(() => setError(null), 5000);
  };

  const refreshData = async () => {
    setPage(1);
    const paginationParams = { skip: 0, limit: PAGE_SIZE };
    try {
      const response = debouncedSearch
        ? await ApiService.searchTableData(
            tablename,
            selectedColumn,
            debouncedSearch,
            paginationParams
          )
        : await ApiService.getTableData(tablename, paginationParams);
      setData(response.data || []);
      setHasMore((response.data?.length || 0) >= PAGE_SIZE);
    } catch {
      showError('Failed to refresh data');
    }
  };

  // CRUD Handlers
  const handleAdd = () => {
    const emptyForm: TableRow = {};
    columns.forEach((col) => (emptyForm[col] = ''));
    setFormData(emptyForm);
    setIsAddModalOpen(true);
  };

  const handleAddSubmit = async () => {
    const emptyFields = columns.filter((col) => {
      const val = formData[col];
      return val === undefined || val === null || String(val).trim() === '';
    });

    if (emptyFields.length > 0) {
      showError(`Please fill in all fields: ${emptyFields.join(', ')}`);
      return;
    }

    setLoading(true);
    try {
      const payload: TableRow = {};
      Object.entries(formData).forEach(([key, value]) => {
        const trimmedValue = String(value).trim();
        if (
          trimmedValue !== '' &&
          !isNaN(Number(trimmedValue)) &&
          trimmedValue === Number(trimmedValue).toString()
        ) {
          payload[key] = Number(trimmedValue);
        } else {
          payload[key] = trimmedValue;
        }
      });

      await ApiService.createRow(tablename, payload, currentUser);
      await refreshData();
      setIsAddModalOpen(false);
      showSuccess('Row added successfully!');
    } catch (err: unknown) {
      if (err instanceof Error) {
        showError(err.message || 'Failed to create item');
      } else {
        showError('Failed to create item');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (row: TableRow) => {
    setSelectedRow(row);
    setFormData({ ...row });
    setIsEditModalOpen(true);
  };

  const handleEditSubmit = async () => {
    if (!selectedRow) return;
    setLoading(true);
    try {
      // Create a copy of formData to avoid mutating state directly if we were using it elsewhere
      const payload: TableRow = { ...formData };

      // Remove 'id' from the payload because the backend forbids updating primary keys
      delete payload.id;

      await ApiService.updateRow(
        tablename,
        selectedRow.id as string,
        payload,
        currentUser
      );
      await refreshData();
      setIsEditModalOpen(false);
      showSuccess('Row updated successfully!');
    } catch (err: unknown) {
      if (err instanceof Error) {
        showError(err.message || 'Failed to update item');
      } else {
        showError('Failed to update item');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteClick = (row: TableRow) => {
    setSelectedRow(row);
    setIsDeleteModalOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!selectedRow) return;
    setLoading(true);
    try {
      await ApiService.deleteRow(
        tablename,
        selectedRow.id as string,
        currentUser
      );
      await refreshData();
      setIsDeleteModalOpen(false);
      showSuccess('Row deleted successfully!');
    } catch (err: unknown) {
      if (err instanceof Error) {
        showError(err.message || 'Failed to delete item');
      } else {
        showError('Failed to delete item');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50">
      {/* HEADER WITH SEARCH */}
      <header className="bg-white/80 backdrop-blur-sm border-b border-slate-200 sticky top-0 z-10">
        <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col md:flex-row md:items-center gap-4 justify-between">
          <div className="flex items-center gap-4 min-w-fit">
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

          {/* Search Controls */}
          <div className="flex-1 w-full md:max-w-2xl flex gap-2">
            <div className="relative shrink-0">
              <select
                value={selectedColumn}
                onChange={(e) => setSelectedColumn(e.target.value)}
                className="appearance-none pl-3 pr-8 py-2.5 h-full text-sm bg-white border border-slate-200 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-[#1c66bb]/30 focus:border-[#1c66bb] text-slate-700 cursor-pointer"
              >
                {columns.map((col) => (
                  <option key={col} value={col}>
                    {col}
                  </option>
                ))}
              </select>
              <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-500">
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M19 9l-7 7-7-7"
                  />
                </svg>
              </div>
            </div>
            <div className="relative flex-1">
              <svg
                className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400"
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
                placeholder={`Search by ${selectedColumn}...`}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 text-sm text-slate-700 bg-white border border-slate-200 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-[#1c66bb]/30 focus:border-[#1c66bb]"
              />
            </div>
          </div>
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        {/* Toast Notifications */}
        {successMessage && (
          <div className="fixed top-20 right-4 z-[60] bg-green-500 text-white px-6 py-3 rounded-xl shadow-lg flex items-center gap-2 animate-in fade-in slide-in-from-top-2">
            <span>{successMessage}</span>
          </div>
        )}
        {error && (
          <div className="fixed top-20 right-4 z-[60] bg-red-500 text-white px-6 py-3 rounded-xl shadow-lg flex items-center gap-2 animate-in fade-in slide-in-from-top-2">
            <span>{error}</span>
          </div>
        )}

        {/* Action Bar */}
        <div className="flex justify-between items-center mb-4">
          <div className="text-sm text-slate-500 px-1">
            Showing {data.length} row{data.length !== 1 ? 's' : ''}
          </div>
          <button
            onClick={handleAdd}
            className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-[#1c66bb] to-[#0d4a8f] text-white font-medium rounded-xl hover:shadow-lg hover:shadow-blue-500/25 transition-all duration-200"
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
                d="M12 4v16m8-8H4"
              />
            </svg>
            Add Row
          </button>
        </div>

        {/* Data Table */}
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  {columns.map((header) => (
                    <th
                      key={header}
                      className="px-6 py-4 text-left text-sm font-semibold text-slate-600 whitespace-nowrap"
                    >
                      {header}
                    </th>
                  ))}
                  <th className="px-6 py-4 text-right text-sm font-semibold text-slate-600 w-24">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.length === 0 && !initialLoading ? (
                  <tr>
                    <td
                      colSpan={columns.length + 1}
                      className="px-6 py-12 text-center text-slate-500"
                    >
                      No data found.
                    </td>
                  </tr>
                ) : (
                  data.map((row, rowIndex) => (
                    <tr
                      key={(row.id as React.Key) ?? rowIndex}
                      className="hover:bg-slate-50 transition-colors group"
                    >
                      {columns.map((col) => (
                        <td
                          key={col}
                          className={`px-6 py-4 text-sm whitespace-nowrap ${
                            row[col] != null
                              ? 'text-slate-700'
                              : 'text-slate-400 italic'
                          }`}
                        >
                          {String(row[col] ?? 'null')}
                        </td>
                      ))}
                      <td className="px-6 py-4 text-right">
                        <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                          <button
                            onClick={() => handleEdit(row)}
                            className="p-2 text-slate-500 hover:text-[#1c66bb] hover:bg-blue-50 rounded-lg transition-colors"
                            title="Edit"
                          >
                            <svg
                              className="w-4 h-4"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"
                              />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleDeleteClick(row)}
                            className="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            title="Delete"
                          >
                            <svg
                              className="w-4 h-4"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                              />
                            </svg>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Loading Spinner / Infinite Scroll Target */}
          <div ref={observerTarget} className="p-6 text-center">
            {(loading || initialLoading) && (
              <div className="inline-block w-6 h-6 border-2 border-[#1c66bb] border-t-transparent rounded-full animate-spin"></div>
            )}
            {!hasMore && data.length > 0 && (
              <span className="text-slate-400 text-sm">End of results</span>
            )}
          </div>
        </div>
      </main>

      {/* MODALS */}
      {(isAddModalOpen || isEditModalOpen) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => {
              if (loading) return;
              setIsAddModalOpen(false);
              setIsEditModalOpen(false);
            }}
          />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] overflow-hidden flex flex-col">
            <div className="px-6 py-4 border-b border-slate-200">
              <h2 className="text-xl font-semibold text-slate-800">
                {isAddModalOpen ? 'Add New Row' : 'Edit Row'}
              </h2>
            </div>
            <div className="px-6 py-4 overflow-y-auto space-y-4">
              {columns.map((col) => (
                <div key={col}>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    {col} <span className="text-red-500">*</span>
                  </label>
                  <input
                    value={String(formData[col] ?? '')}
                    onChange={(e) =>
                      setFormData({ ...formData, [col]: e.target.value })
                    }
                    className={`w-full px-4 py-2 text-slate-700 bg-slate-50 border rounded-xl focus:outline-none focus:ring-2 focus:ring-[#1c66bb]/30 focus:border-[#1c66bb] focus:bg-white transition-all duration-200 ${
                      String(formData[col] ?? '').trim() === ''
                        ? 'border-red-300'
                        : 'border-slate-200'
                    }`}
                    placeholder={`Enter ${col}`}
                  />
                </div>
              ))}
            </div>
            <div className="px-6 py-4 border-t border-slate-200 flex justify-end gap-2">
              <button
                onClick={() => {
                  setIsAddModalOpen(false);
                  setIsEditModalOpen(false);
                }}
                className="px-4 py-2 rounded-xl hover:bg-slate-100"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                onClick={isAddModalOpen ? handleAddSubmit : handleEditSubmit}
                disabled={loading}
                className="px-4 py-2 bg-blue-600 text-white rounded-xl disabled:opacity-50 flex items-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Saving...
                  </>
                ) : (
                  'Save'
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {isDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => !loading && setIsDeleteModalOpen(false)}
          />
          <div className="relative bg-white rounded-2xl p-6 max-w-sm w-full mx-4 text-center">
            <h3 className="text-lg font-semibold mb-2">Delete Row?</h3>
            <p className="text-slate-500 mb-6">This action cannot be undone.</p>
            <div className="flex justify-center gap-4">
              <button
                onClick={() => setIsDeleteModalOpen(false)}
                className="px-4 py-2 hover:bg-slate-100 rounded-xl"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteConfirm}
                disabled={loading}
                className="px-4 py-2 bg-red-600 text-white rounded-xl disabled:opacity-50 flex items-center gap-2"
              >
                {loading ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Deleting...
                  </>
                ) : (
                  'Delete'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
