'use client';

import { useState, useRef, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useServices } from '@/services';
import { FILE_UPLOAD } from '@/constants';
import { Button } from '@/components/Button';

type UploadStatus = 'idle' | 'uploading' | 'success' | 'error';

function deriveTableName(filename: string): string {
  const stem = filename.includes('.')
    ? filename.substring(0, filename.lastIndexOf('.'))
    : filename;
  let name = stem
    .replace(/[^a-zA-Z0-9_]/g, '_')
    .replace(/^_+|_+$/g, '')
    .toLowerCase();
  if (!name || /^\d/.test(name)) {
    name = `t_${name}`;
  }
  return name;
}

export default function DataUploadPage() {
  const router = useRouter();
  const { authService, dataService } = useServices();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>('idle');
  const [errorMessage, setErrorMessage] = useState('');
  const [uploadProgress, setUploadProgress] = useState(0);
  const [tableName, setTableName] = useState('');
  const [duplicateWarning, setDuplicateWarning] = useState('');

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
      validateAndSetFile(e.dataTransfer.files[0]);
    }
  }, []);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (selectedFile: File) => {
    const fileExtension = selectedFile.name
      .toLowerCase()
      .substring(selectedFile.name.lastIndexOf('.'));

    if (
      !FILE_UPLOAD.ALLOWED_TYPES.includes(selectedFile.type) &&
      !FILE_UPLOAD.ALLOWED_EXTENSIONS.includes(fileExtension)
    ) {
      setErrorMessage(
        `Please upload a valid file (${FILE_UPLOAD.ALLOWED_EXTENSIONS.join(', ')})`
      );
      setUploadStatus('error');
      return;
    }

    setFile(selectedFile);
    setTableName(deriveTableName(selectedFile.name));
    setDuplicateWarning('');
    setErrorMessage('');
    setUploadStatus('idle');
  };

  // Check for duplicate table name when it changes
  useEffect(() => {
    if (!tableName) {
      setDuplicateWarning('');
      return;
    }

    const timer = setTimeout(async () => {
      try {
        const result = await dataService.checkDuplicate(tableName);
        setDuplicateWarning(
          result.exists
            ? `A table named "${tableName}" already exists and will be overwritten.`
            : ''
        );
      } catch {
        // Non-blocking: don't prevent upload if check fails
      }
    }, 300);

    return () => clearTimeout(timer);
  }, [tableName, dataService]);

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
      const apiBase = (
        process.env.NEXT_PUBLIC_API_URL || '/api'
      ).replace(/\/$/, '');

      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const progress = Math.round((event.loaded / event.total) * 100);
          setUploadProgress(progress);
        }
      });

      const uploadPromise = new Promise<{ file_id: string }>(
        (resolve, reject) => {
          xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              try {
                const data = JSON.parse(xhr.responseText || '{}') as {
                  file_id?: string;
                };
                if (!data.file_id) {
                  reject(
                    new Error('Upload succeeded, but no file_id was returned')
                  );
                  return;
                }
                resolve({ file_id: data.file_id });
              } catch {
                reject(
                  new Error(
                    'Upload succeeded, but the response was not valid JSON'
                  )
                );
              }
            } else {
              const errorData = JSON.parse(xhr.responseText || '{}');
              reject(
                new Error(
                  errorData.detail || `Upload failed: ${xhr.statusText}`
                )
              );
            }
          };
          xhr.onerror = () => reject(new Error('Network error occurred'));
        }
      );

      const uploadQuery = tableName
        ? `?table_name=${encodeURIComponent(tableName)}`
        : '';
      xhr.open('POST', `${apiBase}/files/upload${uploadQuery}`);
      if (userName) {
        xhr.setRequestHeader('X-User-Name', userName);
      }
      xhr.send(formData);

      const { file_id } = await uploadPromise;
      setUploadStatus('success');
      setUploadProgress(100);

      router.push(
        `/schema-editor?file_id=${encodeURIComponent(file_id)}&file_name=${encodeURIComponent(file.name)}`
      );
    } catch (error) {
      setUploadStatus('error');
      setErrorMessage(
        error instanceof Error ? error.message : 'An unexpected error occurred'
      );
    }
  };

  const resetUpload = () => {
    setFile(null);
    setUploadStatus('idle');
    setErrorMessage('');
    setUploadProgress(0);
    setTableName('');
    setDuplicateWarning('');
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  return (
    <div className="min-h-screen bg-white flex items-center justify-center p-6">
      <main className="w-full max-w-3xl">
        <div className="bg-white rounded-lg p-2">
          {/* Drop Zone */}
          <div
            onDragEnter={handleDrag}
            onDragLeave={handleDrag}
            onDragOver={handleDrag}
            onDrop={handleDrop}
            className={`
              relative flex flex-col items-center justify-center h-64
              border-[3px] border-slate-500
              bg-[#E3F2FD]
              transition-colors duration-200
              ${dragActive ? 'border-blue-500 bg-blue-100' : ''}
            `}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept={FILE_UPLOAD.ALLOWED_EXTENSIONS.join(',')}
              onChange={handleFileChange}
              className="hidden"
            />

            {/* Upload Icon */}
            <div className="mb-4">
              <svg
                width="40"
                height="40"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="text-slate-800"
              >
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>

            <p className="text-lg text-slate-900 mb-1">Drag and drop</p>
            <p className="text-lg text-slate-900 mb-4">or</p>

            <button
              onClick={() => fileInputRef.current?.click()}
              className="bg-[#CFCFCF] hover:bg-gray-300 text-slate-800 border border-slate-500 px-10 py-2 rounded shadow-sm text-lg font-normal transition-colors"
            >
              Choose file
            </button>
          </div>

          {/* Uploaded File Section */}
          {file && (
            <div className="mt-8">
              <h3 className="text-lg font-medium text-slate-900 mb-2">
                Uploaded File
              </h3>
              <div className="flex items-center justify-between border-[2px] border-[#68B96A] rounded p-3 bg-[#F1F8E9]">
                <div className="text-[#68B96A]">
                  <svg
                    width="28"
                    height="28"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.5"
                  >
                    <circle cx="12" cy="12" r="10" />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M8.5 12.5L10.5 14.5L15.5 9.5"
                    />
                  </svg>
                </div>
                <span className="flex-1 px-4 text-slate-900 font-semibold text-lg truncate">
                  {file.name}
                </span>
                <button
                  onClick={resetUpload}
                  className="text-slate-700 hover:text-red-600 transition-colors"
                >
                  <svg
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  >
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    <line x1="10" y1="11" x2="10" y2="17" />
                    <line x1="14" y1="11" x2="14" y2="17" />
                  </svg>
                </button>
              </div>
            </div>
          )}

          {/* Table Name */}
          {file && (
            <div className="mt-6">
              <label
                htmlFor="table-name"
                className="block text-sm font-medium text-slate-700 mb-1"
              >
                Table name
              </label>
              <input
                id="table-name"
                value={tableName}
                onChange={(e) =>
                  setTableName(
                    e.target.value.replace(/[^a-zA-Z0-9_]/g, '').toLowerCase()
                  )
                }
                className="w-full border-[2px] border-slate-500 rounded px-4 py-2 text-slate-900"
              />
              {duplicateWarning && (
                <div className="mt-2 p-3 border border-amber-400 bg-amber-50 rounded text-sm text-amber-800">
                  {duplicateWarning}
                </div>
              )}
            </div>
          )}

          {/* Status Messages */}
          {uploadStatus === 'error' && errorMessage && (
            <div className="mt-4 text-red-600 text-sm font-medium">
              {errorMessage}
            </div>
          )}
          {uploadStatus === 'uploading' && (
            <div className="mt-4 w-full bg-slate-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          )}
          {uploadStatus === 'success' && (
            <div className="mt-4 text-green-600 text-sm font-medium">
              Upload Complete!
            </div>
          )}

          {/* Action Buttons */}
          <div className="flex justify-end gap-4 mt-12">
            <Button
              variant="secondary"
              onClick={() => router.push('/')}
              className="px-10"
            >
              Cancel
            </Button>
            <button
              onClick={handleUpload}
              disabled={!file || uploadStatus === 'uploading'}
              className="px-8 py-2.5 bg-[#CFE8F8] border border-slate-500 rounded text-slate-900 font-medium hover:bg-[#badcf5] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {uploadStatus === 'uploading' ? 'Uploading...' : 'Verify Columns'}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}
