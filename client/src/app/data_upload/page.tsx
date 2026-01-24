'use client';

import { useState, useRef, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { useServices } from '@/services';

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

export default function DataUploadPage() {
  const router = useRouter();
  const { authService } = useServices();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);

  const handleDrag = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      validateAndSetFile(droppedFile);
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile: File) => {
    const allowedTypes = [
      'text/csv',
      'application/vnd.ms-excel'
    ];
    const allowedExtensions = ['.csv', '.xlsx'];

    const fileExtension = selectedFile.name
      .toLowerCase()
      .substring(selectedFile.name.lastIndexOf('.'));

    if (
      !allowedTypes.includes(selectedFile.type) &&
      !allowedExtensions.includes(fileExtension)
    ) {
      setErrorMessage('Please upload a CSV or Excel file (.csv, .xlsx)');
      setUploadStatus('error');
      return;
    }

    setFile(selectedFile);
    setErrorMessage('');
    setUploadStatus('idle');
  };

  const handleUpload = async () => {
    if (!file) {
      setErrorMessage('Please select a file');
      setUploadStatus('error');
      return;
    }

    setUploadStatus('uploading');
    setUploadProgress(0);
    setErrorMessage('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const userName = await authService.getCurrentUserName();
      const baseUrl =
        process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';

      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const progress = Math.round((event.loaded / event.total) * 100);
          setUploadProgress(progress);
        }
      });

      const uploadPromise = new Promise<void>((resolve, reject) => {
        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            const errorData = JSON.parse(xhr.responseText || '{}');
            reject(new Error(errorData.detail || `Upload failed: ${xhr.statusText}`));
          }
        };
        xhr.onerror = () => reject(new Error('Network error occurred'));
      });

      xhr.open('POST', `${baseUrl}/api/files/upload`);
      if (userName) {
        xhr.setRequestHeader('X-User-Name', userName);
      }
      xhr.send(formData);

      await uploadPromise;

      setUploadStatus('success');
      setUploadProgress(100);
    } catch (error) {
      setUploadStatus('error');
      setErrorMessage(
        error instanceof Error ? error.message : 'An unexpected error occurred'
      );
    }
  };

  const handleSignOut = async () => {
    await authService.signOut();
    router.push('/login');
  };

  const resetUpload = () => {
    setFile(null);
    setUploadStatus('idle');
    setErrorMessage('');
    setUploadProgress(0);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
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
          <div className="flex items-center gap-3">
            <button
              onClick={() => router.push('/homescreen')}
              className="px-4 py-2 text-sm font-medium text-slate-600 bg-slate-100 border border-slate-200 rounded-lg hover:bg-slate-200 transition-all duration-200"
            >
              Back to Tables
            </button>
            <button
              onClick={handleSignOut}
              className="px-4 py-2 text-sm font-medium text-red-600 bg-red-50 border border-red-200 rounded-lg hover:bg-red-100 hover:border-red-300 transition-all duration-200"
            >
              Sign Out
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-12">
        <div className="bg-white rounded-2xl shadow-sm border border-slate-200 overflow-hidden">
          {/* Page Title */}
          <div className="px-8 py-6 border-b border-slate-200">
            <h2 className="text-2xl font-semibold text-slate-800">
              Upload Data
            </h2>
            <p className="text-slate-500 mt-1">
              Upload a CSV or Excel file to create a new data table
            </p>
          </div>

          <div className="px-8 py-8 space-y-8">
            {/* File Drop Zone */}
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-3">
                Select File
              </label>
              <div
                onDragEnter={handleDrag}
                onDragLeave={handleDrag}
                onDragOver={handleDrag}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`relative border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-all duration-200 ${
                  dragActive
                    ? 'border-[#1c66bb] bg-blue-50'
                    : file
                      ? 'border-green-300 bg-green-50'
                      : 'border-slate-300 hover:border-[#1c66bb] hover:bg-slate-50'
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".csv,.xlsx"
                  onChange={handleFileChange}
                  className="hidden"
                />

                {file ? (
                  <div className="space-y-2">
                    <div className="w-12 h-12 mx-auto rounded-xl bg-green-100 flex items-center justify-center">
                      <svg
                        className="w-6 h-6 text-green-600"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                        />
                      </svg>
                    </div>
                    <p className="text-slate-800 font-medium">{file.name}</p>
                    <p className="text-slate-500 text-sm">
                      {formatFileSize(file.size)}
                    </p>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        resetUpload();
                      }}
                      className="text-sm text-red-600 hover:text-red-700 font-medium"
                    >
                      Remove file
                    </button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="w-12 h-12 mx-auto rounded-xl bg-slate-100 flex items-center justify-center">
                      <svg
                        className="w-6 h-6 text-slate-400"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
                        />
                      </svg>
                    </div>
                    <div>
                      <p className="text-slate-700 font-medium">
                        Drop your file here, or{' '}
                        <span className="text-[#1c66bb]">browse</span>
                      </p>
                      <p className="text-slate-500 text-sm mt-1">
                        Supports CSV and XLSX files
                      </p>
                    </div>
                  </div>
                )}
              </div>
            </div>

            {/* Error Message */}
            {uploadStatus === 'error' && errorMessage && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-xl flex items-start gap-3">
                <svg
                  className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <p className="text-red-600 text-sm">{errorMessage}</p>
              </div>
            )}

            {/* Success Message */}
            {uploadStatus === 'success' && (
              <div className="p-4 bg-green-50 border border-green-200 rounded-xl flex items-start gap-3">
                <svg
                  className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"
                  />
                </svg>
                <p className="text-green-600 font-medium">Upload successful!</p>
              </div>
            )}

            {/* Upload Progress */}
            {uploadStatus === 'uploading' && (
              <div className="space-y-2">
                <div className="flex items-center justify-between text-sm">
                  <span className="text-slate-600">Uploading...</span>
                  <span className="text-slate-600 font-medium">
                    {uploadProgress}%
                  </span>
                </div>
                <div className="h-2 bg-slate-200 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-gradient-to-r from-[#1c66bb] to-[#0d4a8f] transition-all duration-300"
                    style={{ width: `${uploadProgress}%` }}
                  />
                </div>
              </div>
            )}

            {/* Upload Button */}
            <div className="flex justify-end gap-3 pt-4">
              <button
                onClick={resetUpload}
                disabled={uploadStatus === 'uploading'}
                className="px-6 py-3 text-slate-600 font-medium bg-slate-100 border border-slate-200 rounded-xl hover:bg-slate-200 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Reset
              </button>
              <button
                onClick={handleUpload}
                disabled={!file || uploadStatus === 'uploading'}
                className="px-6 py-3 bg-gradient-to-r from-[#1c66bb] to-[#0d4a8f] text-white font-medium rounded-xl hover:shadow-lg hover:shadow-blue-500/25 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {uploadStatus === 'uploading' ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Uploading...
                  </>
                ) : (
                  <>
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
                        d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                      />
                    </svg>
                    Upload File
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
