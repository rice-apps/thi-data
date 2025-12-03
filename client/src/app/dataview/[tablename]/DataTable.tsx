"use client";

import { useState } from "react";

interface DataTableProps {
  tablename: string;
  initialData: Record<string, any>[];
  columns: string[];
}

export default function DataTable({ tablename, initialData, columns }: DataTableProps) {
  const [data, setData] = useState(initialData);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);
  const [selectedRow, setSelectedRow] = useState<Record<string, any> | null>(null);
  const [formData, setFormData] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const backendUrl = "http://localhost:8000";

  const showSuccess = (msg: string) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 3000);
  };

  const showError = (msg: string) => {
    setError(msg);
    setTimeout(() => setError(null), 5000);
  };

  const refreshData = async () => {
    try {
      const resp = await fetch(`${backendUrl}/api/${encodeURIComponent(tablename)}`);
      if (!resp.ok) throw new Error("Failed to fetch data");
      const newData = await resp.json();
      setData(newData);
    } catch (err: any) {
      showError(err.message);
    }
  };

  // CREATE
  const handleAdd = () => {
    const emptyForm: Record<string, any> = {};
    columns.forEach((col) => {
      emptyForm[col] = "";
    });
    setFormData(emptyForm);
    setError(null);
    setIsAddModalOpen(true);
  };

  const handleAddSubmit = async () => {
    const emptyFields = columns.filter((col) => !formData[col] || formData[col].toString().trim() === "");
    if (emptyFields.length > 0) {
      showError(`Please fill in all fields: ${emptyFields.join(", ")}`);
      return;
    }

    setLoading(true);
    try {
      const payload: Record<string, any> = {};
      Object.entries(formData).forEach(([key, value]) => {
        const trimmedValue = String(value).trim();
        if (trimmedValue !== "" && !isNaN(Number(trimmedValue)) && trimmedValue === Number(trimmedValue).toString()) {
          payload[key] = Number(trimmedValue);
        } else {
          payload[key] = trimmedValue;
        }
      });

      const resp = await fetch(`${backendUrl}/api/table/${encodeURIComponent(tablename)}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to create item");
      }

      await refreshData();
      setIsAddModalOpen(false);
      showSuccess("Row added successfully!");
    } catch (err: any) {
      showError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // EDIT
  const handleEdit = (row: Record<string, any>) => {
    setSelectedRow(row);
    const editForm: Record<string, any> = {};
    columns.forEach((col) => {
      editForm[col] = row[col] ?? "";
    });
    setFormData(editForm);
    setError(null);
    setIsEditModalOpen(true);
  };

  const handleEditSubmit = async () => {
    if (!selectedRow) return;

    setLoading(true);
    try {
      const payload: Record<string, any> = {};
      Object.entries(formData).forEach(([key, value]) => {
        const trimmedValue = String(value).trim();
        const originalValue = selectedRow[key];

        if (trimmedValue !== String(originalValue ?? "")) {
          if (trimmedValue !== "" && !isNaN(Number(trimmedValue)) && trimmedValue === Number(trimmedValue).toString()) {
            payload[key] = Number(trimmedValue);
          } else if (trimmedValue === "") {
            payload[key] = null;
          } else {
            payload[key] = trimmedValue;
          }
        }
      });

      if (Object.keys(payload).length === 0) {
        setIsEditModalOpen(false);
        return;
      }

      const resp = await fetch(
        `${backendUrl}/api/${encodeURIComponent(tablename)}/${selectedRow.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        }
      );

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to update item");
      }

      await refreshData();
      setIsEditModalOpen(false);
      showSuccess("Row updated successfully!");
    } catch (err: any) {
      showError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // DELETE
  const handleDeleteClick = (row: Record<string, any>) => {
    setSelectedRow(row);
    setIsDeleteModalOpen(true);
  };

  const handleDeleteConfirm = async () => {
    if (!selectedRow) return;
    setLoading(true);
    try {
      const resp = await fetch(
        `${backendUrl}/api/${encodeURIComponent(tablename)}/${selectedRow.id}`,
        { method: "DELETE" }
      );

      if (!resp.ok) {
        const errData = await resp.json().catch(() => ({}));
        throw new Error(errData.detail || "Failed to delete item");
      }

      await refreshData();
      setIsDeleteModalOpen(false);
      showSuccess("Row deleted successfully!");
    } catch (err: any) {
      showError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      {/* Toast Notifications */}
      {successMessage && (
        <div className="fixed top-4 right-4 z-50 bg-green-500 text-white px-6 py-3 rounded-xl shadow-lg flex items-center gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          {successMessage}
        </div>
      )}
      {error && (
        <div className="fixed top-4 right-4 z-50 bg-red-500 text-white px-6 py-3 rounded-xl shadow-lg flex items-center gap-2">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
          {error}
        </div>
      )}

      {/* Action Bar */}
      <div className="flex justify-between items-center mb-4">
        <p className="text-sm text-slate-500">
          {data.length} row{data.length !== 1 ? "s" : ""} • {columns.length} column{columns.length !== 1 ? "s" : ""}
        </p>
        <button
          onClick={handleAdd}
          className="flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-[#1c66bb] to-[#0d4a8f] text-white font-medium rounded-xl hover:shadow-lg hover:shadow-blue-500/25 transition-all duration-200"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
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
                <th className="px-6 py-4 text-right text-sm font-semibold text-slate-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {data.length === 0 ? (
                <tr>
                  <td colSpan={columns.length + 1} className="px-6 py-12 text-center text-slate-500">
                    No data yet. Click "Add Row" to create your first entry.
                  </td>
                </tr>
              ) : (
                data.map((row, rowIndex) => (
                  <tr key={row.id ?? rowIndex} className="hover:bg-slate-50 transition-colors group">
                    {columns.map((col) => (
                      <td
                        key={col}
                        className={`px-6 py-4 text-sm whitespace-nowrap ${
                          row[col] != null ? "text-slate-700" : "text-slate-400 italic"
                        }`}
                      >
                        {row[col] ?? "null"}
                      </td>
                    ))}
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                        <button
                          onClick={() => handleEdit(row)}
                          className="p-2 text-slate-500 hover:text-[#1c66bb] hover:bg-blue-50 rounded-lg transition-colors"
                          title="Edit"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button
                          onClick={() => handleDeleteClick(row)}
                          className="p-2 text-slate-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                          title="Delete"
                        >
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
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
      </div>

      {/* Add/Edit Modal */}
      {(isAddModalOpen || isEditModalOpen) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => {
              setIsAddModalOpen(false);
              setIsEditModalOpen(false);
            }}
          />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-lg mx-4 max-h-[80vh] overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200">
              <h2 className="text-xl font-semibold text-slate-800">
                {isAddModalOpen ? "Add New Row" : "Edit Row"}
              </h2>
            </div>
            <div className="px-6 py-4 overflow-y-auto max-h-[60vh] space-y-4">
              {columns.map((col) => (
                <div key={col}>
                  <label className="block text-sm font-medium text-slate-700 mb-1">
                    {col} <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={formData[col] ?? ""}
                    onChange={(e) => setFormData({ ...formData, [col]: e.target.value })}
                    className={`w-full px-4 py-2 text-slate-700 bg-slate-50 border rounded-xl focus:outline-none focus:ring-2 focus:ring-[#1c66bb]/30 focus:border-[#1c66bb] focus:bg-white transition-all duration-200 ${
                      formData[col]?.toString().trim() === "" ? "border-red-300" : "border-slate-200"
                    }`}
                    placeholder={`Enter ${col}`}
                  />
                </div>
              ))}
            </div>
            <div className="px-6 py-4 border-t border-slate-200 flex justify-end gap-3">
              <button
                onClick={() => {
                  setIsAddModalOpen(false);
                  setIsEditModalOpen(false);
                }}
                className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-xl transition-colors"
                disabled={loading}
              >
                Cancel
              </button>
              <button
                onClick={isAddModalOpen ? handleAddSubmit : handleEditSubmit}
                disabled={loading}
                className="px-4 py-2 bg-gradient-to-r from-[#1c66bb] to-[#0d4a8f] text-white font-medium rounded-xl hover:shadow-lg hover:shadow-blue-500/25 transition-all duration-200 disabled:opacity-50"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                    Saving...
                  </span>
                ) : isAddModalOpen ? (
                  "Add Row"
                ) : (
                  "Save Changes"
                )}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {isDeleteModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setIsDeleteModalOpen(false)}
          />
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-md mx-4 p-6">
            <div className="text-center">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-red-100 flex items-center justify-center">
                <svg className="w-8 h-8 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-slate-800 mb-2">Delete Row?</h2>
              <p className="text-slate-500 mb-6">
                This action cannot be undone. This will permanently delete the selected row.
              </p>
              <div className="flex justify-center gap-3">
                <button
                  onClick={() => setIsDeleteModalOpen(false)}
                  className="px-6 py-2 text-slate-600 hover:bg-slate-100 rounded-xl transition-colors"
                  disabled={loading}
                >
                  Cancel
                </button>
                <button
                  onClick={handleDeleteConfirm}
                  disabled={loading}
                  className="px-6 py-2 bg-red-600 text-white font-medium rounded-xl hover:bg-red-700 transition-colors disabled:opacity-50"
                >
                  {loading ? (
                    <span className="flex items-center gap-2">
                      <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                      Deleting...
                    </span>
                  ) : (
                    "Delete"
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
