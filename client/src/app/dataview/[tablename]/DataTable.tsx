'use client';

import { useState, useEffect, useRef, useCallback } from 'react';
import Link from 'next/link';
import { useServices } from '@/services';
import { UI, COLORS } from '@/constants';
import { Toast, useToast } from '@/components/Toast';
import { ConfirmModal } from '@/components/ConfirmModal';
import { Modal, ModalBody, ModalFooter } from '@/components/Modal';
import { Button } from '@/components/Button';
import { Spinner } from '@/components/Spinner';
import { SearchInput } from '@/components/SearchInput';
import type { TableRow, CellError, PaginationParams } from '@/types';
import { formatValue } from '@/utils/formatters';

type DataTableProps = {
  tablename: string;
  initialData: TableRow[];
  columns: string[];
};

export default function DataTable({
  tablename,
  initialData,
  columns,
}: DataTableProps) {
  const { dataService } = useServices();
  const { toast, showSuccess, showError, hideToast } = useToast();

  const [data, setData] = useState<TableRow[]>(initialData);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(true);
  const [loading, setLoading] = useState(false);
  const [initialLoading, setInitialLoading] = useState(false);

  const [search, setSearch] = useState('');
  const [selectedColumn, setSelectedColumn] = useState(columns[0] || 'id');
  const [debouncedSearch, setDebouncedSearch] = useState('');

  const [modalState, setModalState] = useState<{
    type: 'add' | 'edit' | 'delete' | 'resolve' | null;
    row?: TableRow;
    field?: string;
  }>({ type: null });
  const [formData, setFormData] = useState<TableRow>({});
  const [resolveValue, setResolveValue] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const observerTarget = useRef<HTMLDivElement>(null);
  const isFirstRender = useRef(true);

  // Debounce search input
  useEffect(() => {
    const handler = setTimeout(
      () => setDebouncedSearch(search),
      UI.DEBOUNCE_MS
    );
    return () => clearTimeout(handler);
  }, [search]);

  // Fetch data when search changes
  useEffect(() => {
    if (isFirstRender.current) {
      isFirstRender.current = false;
      return;
    }

    const fetchFirstPage = async () => {
      setInitialLoading(true);
      setPage(1);
      try {
        const params: PaginationParams = { skip: 0, limit: UI.PAGE_SIZE };
        const response = debouncedSearch
          ? await dataService.searchTableData(
              tablename,
              selectedColumn,
              debouncedSearch,
              params
            )
          : await dataService.getTableData(tablename, params);

        setData(response.data || []);
        setHasMore((response.data?.length || 0) >= UI.PAGE_SIZE);
      } catch {
        showError('Failed to search data');
      } finally {
        setInitialLoading(false);
      }
    };

    fetchFirstPage();
  }, [debouncedSearch, selectedColumn, tablename, dataService, showError]);

  const loadMore = useCallback(async () => {
    if (loading || !hasMore) return;

    setLoading(true);
    try {
      const skip = page * UI.PAGE_SIZE;
      const params: PaginationParams = { skip, limit: UI.PAGE_SIZE };
      const response = debouncedSearch
        ? await dataService.searchTableData(
            tablename,
            selectedColumn,
            debouncedSearch,
            params
          )
        : await dataService.getTableData(tablename, params);

      const newData = response.data || [];
      if (newData.length < UI.PAGE_SIZE) setHasMore(false);

      setData((prev) => [...prev, ...newData]);
      setPage((prev) => prev + 1);
    } catch {
      showError('Failed to load more data');
    } finally {
      setLoading(false);
    }
  }, [
    page,
    loading,
    hasMore,
    debouncedSearch,
    selectedColumn,
    tablename,
    dataService,
    showError,
  ]);

  // Infinite scroll observer
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
    if (element) observer.observe(element);
    return () => {
      if (element) observer.unobserve(element);
    };
  }, [loadMore, hasMore, loading, initialLoading]);

  const refreshData = async () => {
    setPage(1);
    const params: PaginationParams = { skip: 0, limit: UI.PAGE_SIZE };
    try {
      const response = debouncedSearch
        ? await dataService.searchTableData(
            tablename,
            selectedColumn,
            debouncedSearch,
            params
          )
        : await dataService.getTableData(tablename, params);
      setData(response.data || []);
      setHasMore((response.data?.length || 0) >= UI.PAGE_SIZE);
    } catch {
      showError('Failed to refresh data');
    }
  };

  const handleAdd = () => {
    const emptyForm: TableRow = {};
    columns.forEach((col) => (emptyForm[col] = ''));
    setFormData(emptyForm);
    setModalState({ type: 'add' });
  };

  const handleEdit = (row: TableRow) => {
    setFormData({ ...row });
    setModalState({ type: 'edit', row });
  };

  const handleDelete = (row: TableRow) => {
    setModalState({ type: 'delete', row });
  };

  const handleResolve = (row: TableRow, field: string) => {
    const cellError = row._error_context?.[field];
    setResolveValue(cellError?.raw_value ?? '');
    setModalState({ type: 'resolve', row, field });
  };

  const closeModal = () => {
    if (!submitting) setModalState({ type: null });
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

    setSubmitting(true);
    try {
      const payload: TableRow = {};
      Object.entries(formData).forEach(([key, value]) => {
        const trimmed = String(value).trim();
        payload[key] =
          !isNaN(Number(trimmed)) && trimmed === Number(trimmed).toString()
            ? Number(trimmed)
            : trimmed;
      });

      await dataService.createRow(tablename, payload);
      await refreshData();
      closeModal();
      showSuccess('Row added successfully!');
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to create item');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEditSubmit = async () => {
    if (!modalState.row) return;
    setSubmitting(true);
    try {
      const payload = { ...formData };
      delete payload.id;
      await dataService.updateRow(
        tablename,
        modalState.row.id as string,
        payload
      );
      await refreshData();
      closeModal();
      showSuccess('Row updated successfully!');
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to update item');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteConfirm = async () => {
    if (!modalState.row) return;
    setSubmitting(true);
    try {
      await dataService.deleteRow(tablename, modalState.row.id as string);
      await refreshData();
      closeModal();
      showSuccess('Row deleted successfully!');
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to delete item');
    } finally {
      setSubmitting(false);
    }
  };

  const handleResolveSubmit = async () => {
    if (!modalState.row || !modalState.field) return;
    setSubmitting(true);
    try {
      await dataService.updateRow(tablename, modalState.row.id as string, {
        [modalState.field]: resolveValue,
      });

      // Optimistic UI update
      setData((prev) =>
        prev.map((r) => {
          if (r.id !== modalState.row!.id) return r;
          const updatedContext = { ...r._error_context };
          delete updatedContext[modalState.field!];
          const stillCorrupted = Object.keys(updatedContext).length > 0;
          return {
            ...r,
            [modalState.field!]: resolveValue,
            _is_corrupted: stillCorrupted,
            _error_context: stillCorrupted ? updatedContext : undefined,
          } as TableRow;
        })
      );

      closeModal();
      showSuccess(`"${modalState.field}" resolved successfully!`);
    } catch (err) {
      showError(err instanceof Error ? err.message : 'Failed to resolve value');
    } finally {
      setSubmitting(false);
    }
  };

  const renderCell = (row: TableRow, col: string) => {
    const cellError = row._error_context?.[col];
    const isCellCorrupted = row[col] == null && !!cellError;

    if (isCellCorrupted) {
      return (
        <CorruptedCell
          cellError={cellError}
          onClick={() => handleResolve(row, col)}
        />
      );
    }

    return formatValue(row[col], 'null');
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50">
      {toast && (
        <Toast message={toast.message} type={toast.type} onClose={hideToast} />
      )}

      <Header
        tablename={tablename}
        columns={columns}
        selectedColumn={selectedColumn}
        onColumnChange={setSelectedColumn}
        search={search}
        onSearchChange={setSearch}
      />

      <main className="max-w-7xl mx-auto px-6 py-8">
        <div className="flex justify-between items-center mb-4">
          <div className="text-sm text-slate-500 px-1">
            Showing {data.length} row{data.length !== 1 ? 's' : ''}
          </div>
          <Button onClick={handleAdd}>
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
          </Button>
        </div>

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
                  data.map((row, rowIndex) => {
                    const isCorrupted = row._is_corrupted === true;
                    return (
                      <tr
                        key={(row.id as React.Key) ?? rowIndex}
                        className={`transition-colors group ${
                          isCorrupted
                            ? 'bg-red-50 border-l-4 border-red-400 hover:bg-red-100'
                            : 'hover:bg-slate-50'
                        }`}
                      >
                        {columns.map((col) => {
                          const cellError = row._error_context?.[col];
                          const isCellCorrupted =
                            row[col] == null && !!cellError;
                          return (
                            <td
                              key={col}
                              className={`px-6 py-4 text-sm whitespace-nowrap ${
                                isCellCorrupted
                                  ? 'text-red-600'
                                  : row[col] != null
                                    ? 'text-slate-700'
                                    : 'text-slate-400 italic'
                              }`}
                            >
                              {renderCell(row, col)}
                            </td>
                          );
                        })}
                        <td className="px-6 py-4 text-right">
                          <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                            <ActionButton
                              icon="edit"
                              onClick={() => handleEdit(row)}
                              title="Edit"
                            />
                            <ActionButton
                              icon="delete"
                              onClick={() => handleDelete(row)}
                              title="Delete"
                              variant="danger"
                            />
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>

          <div ref={observerTarget} className="p-6 text-center">
            {(loading || initialLoading) && <Spinner />}
            {!hasMore && data.length > 0 && (
              <span className="text-slate-400 text-sm">End of results</span>
            )}
          </div>
        </div>
      </main>

      {/* Add/Edit Modal */}
      {(modalState.type === 'add' || modalState.type === 'edit') && (
        <Modal
          isOpen={true}
          onClose={closeModal}
          title={modalState.type === 'add' ? 'Add New Row' : 'Edit Row'}
          disableClose={submitting}
        >
          <ModalBody className="space-y-4">
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
                  className={`w-full px-4 py-2 text-slate-700 bg-slate-50 border rounded-xl focus:outline-none focus:ring-2 focus:ring-[${COLORS.PRIMARY}]/30 focus:border-[${COLORS.PRIMARY}] focus:bg-white transition-all duration-200 ${
                    String(formData[col] ?? '').trim() === ''
                      ? 'border-red-300'
                      : 'border-slate-200'
                  }`}
                  placeholder={`Enter ${col}`}
                />
              </div>
            ))}
          </ModalBody>
          <ModalFooter>
            <Button variant="ghost" onClick={closeModal} disabled={submitting}>
              Cancel
            </Button>
            <Button
              onClick={
                modalState.type === 'add' ? handleAddSubmit : handleEditSubmit
              }
              loading={submitting}
            >
              Save
            </Button>
          </ModalFooter>
        </Modal>
      )}

      {/* Delete Modal */}
      <ConfirmModal
        isOpen={modalState.type === 'delete'}
        onClose={closeModal}
        onConfirm={handleDeleteConfirm}
        title="Delete Row?"
        message="This action cannot be undone."
        confirmLabel="Delete"
        loading={submitting}
      />

      {/* Resolve Modal */}
      {modalState.type === 'resolve' && modalState.row && modalState.field && (
        <ResolveModal
          isOpen={true}
          onClose={closeModal}
          onSubmit={handleResolveSubmit}
          field={modalState.field}
          cellError={modalState.row._error_context?.[modalState.field]}
          value={resolveValue}
          onChange={setResolveValue}
          loading={submitting}
        />
      )}
    </div>
  );
}

// Sub-components
function Header({
  tablename,
  columns,
  selectedColumn,
  onColumnChange,
  search,
  onSearchChange,
}: {
  tablename: string;
  columns: string[];
  selectedColumn: string;
  onColumnChange: (col: string) => void;
  search: string;
  onSearchChange: (val: string) => void;
}) {
  return (
    <header className="bg-white/80 backdrop-blur-sm border-b border-slate-200 sticky top-0 z-10">
      <div className="max-w-7xl mx-auto px-6 py-4 flex flex-col md:flex-row md:items-center gap-4 justify-between">
        <div className="flex items-center gap-4 min-w-fit">
          <Link
            href="/homescreen"
            className={`p-2 -ml-2 text-slate-500 hover:text-[${COLORS.PRIMARY}] hover:bg-slate-100 rounded-lg transition-all duration-200`}
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

        <div className="flex-1 w-full md:max-w-2xl flex gap-2">
          <div className="relative shrink-0">
            <select
              value={selectedColumn}
              onChange={(e) => onColumnChange(e.target.value)}
              className={`appearance-none pl-3 pr-8 py-2.5 h-full text-sm bg-white border border-slate-200 rounded-xl shadow-sm focus:outline-none focus:ring-2 focus:ring-[${COLORS.PRIMARY}]/30 focus:border-[${COLORS.PRIMARY}] text-slate-700 cursor-pointer`}
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
          <SearchInput
            value={search}
            onChange={onSearchChange}
            placeholder={`Search by ${selectedColumn}...`}
            className="flex-1"
          />
        </div>
      </div>
    </header>
  );
}

function ActionButton({
  icon,
  onClick,
  title,
  variant = 'default',
}: {
  icon: 'edit' | 'delete';
  onClick: () => void;
  title: string;
  variant?: 'default' | 'danger';
}) {
  const hoverClass =
    variant === 'danger'
      ? 'hover:text-red-600 hover:bg-red-50'
      : `hover:text-[${COLORS.PRIMARY}] hover:bg-blue-50`;

  const iconPath =
    icon === 'edit'
      ? 'M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z'
      : 'M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16';

  return (
    <button
      onClick={onClick}
      className={`p-2 text-slate-500 ${hoverClass} rounded-lg transition-colors`}
      title={title}
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
          d={iconPath}
        />
      </svg>
    </button>
  );
}

function CorruptedCell({
  cellError,
  onClick,
}: {
  cellError: CellError;
  onClick: () => void;
}) {
  return (
    <span className="relative inline-flex items-center gap-1.5 group/cell">
      <button
        onClick={onClick}
        className="inline-flex items-center gap-1.5 cursor-pointer hover:underline"
        title="Click to fix this value"
      >
        <svg
          className="w-4 h-4 text-amber-500 shrink-0"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
          />
        </svg>
        <span className="line-through opacity-75">{cellError.raw_value}</span>
      </button>
      <span className="pointer-events-none absolute left-0 bottom-full mb-2 z-20 hidden group-hover/cell:block w-64 p-3 bg-slate-800 text-white text-xs rounded-lg shadow-lg">
        <span className="block font-semibold mb-1">Validation Error</span>
        <span className="block text-slate-300 mb-1">
          Raw: {'"'}
          {cellError.raw_value}
          {'"'}
        </span>
        <span className="block text-slate-300">{cellError.error}</span>
        <span className="block text-amber-300 mt-1.5 text-[11px]">
          Click to fix
        </span>
      </span>
    </span>
  );
}

function ResolveModal({
  isOpen,
  onClose,
  onSubmit,
  field,
  cellError,
  value,
  onChange,
  loading,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: () => void;
  field: string;
  cellError?: CellError;
  value: string;
  onChange: (val: string) => void;
  loading: boolean;
}) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      disableClose={loading}
      className="max-w-md"
    >
      <div className="px-6 py-4 border-b border-slate-200 flex items-center gap-3">
        <div className="p-2 bg-amber-100 rounded-lg">
          <svg
            className="w-5 h-5 text-amber-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
            />
          </svg>
        </div>
        <div>
          <h2 className="text-lg font-semibold text-slate-800">
            Fix Corrupted Value
          </h2>
          <p className="text-sm text-slate-500">
            Column: <span className="font-medium text-slate-700">{field}</span>
          </p>
        </div>
      </div>
      <ModalBody className="space-y-4">
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 space-y-2">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-medium text-red-700">Original value:</span>
            <code className="px-2 py-0.5 bg-red-100 rounded text-red-800 text-xs">
              {cellError?.raw_value ?? '—'}
            </code>
          </div>
          <p className="text-sm text-red-600">
            {cellError?.error ?? 'Validation failed'}
          </p>
        </div>
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-1.5">
            Corrected value
          </label>
          <input
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className="w-full px-4 py-2.5 text-slate-700 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-amber-500/30 focus:border-amber-500 focus:bg-white transition-all duration-200"
            placeholder={`Enter corrected ${field}`}
            autoFocus
          />
        </div>
      </ModalBody>
      <ModalFooter>
        <Button variant="ghost" onClick={onClose} disabled={loading}>
          Cancel
        </Button>
        <button
          onClick={onSubmit}
          disabled={loading || value.trim() === ''}
          className="px-4 py-2 bg-amber-500 text-white rounded-xl disabled:opacity-50 hover:bg-amber-600 flex items-center gap-2 transition-colors"
        >
          {loading ? (
            <>
              <Spinner size="sm" color="#fff" />
              Resolving...
            </>
          ) : (
            'Resolve'
          )}
        </button>
      </ModalFooter>
    </Modal>
  );
}
