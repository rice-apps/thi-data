'use client';

import { Suspense, useEffect, useState } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { useServices } from '@/services';
import { useProcessing } from '@/components/ProcessingProvider';

type EditableSchemaField = {
  originalName: string;
  name: string;
  type: string;
};

type TypeOption = {
  value: string;
  label: string;
};

const TYPE_OPTIONS: TypeOption[] = [
  { value: 'VARCHAR', label: 'String' },
  { value: 'INTEGER', label: 'Integer' },
  { value: 'DOUBLE', label: 'Decimal' },
  { value: 'BOOLEAN', label: 'True/False' },
  { value: 'DATE', label: 'Date' },
  { value: 'TIMESTAMP', label: 'Timestamp' },
];

const frictionlessTypeToDuckdbType = (frictionlessType?: string): string => {
  const key = (frictionlessType || '').toLowerCase();
  switch (key) {
    case 'string':
      return 'VARCHAR';
    case 'integer':
      return 'INTEGER';
    case 'number':
      return 'DOUBLE';
    case 'boolean':
      return 'BOOLEAN';
    case 'date':
      return 'DATE';
    case 'datetime':
      return 'TIMESTAMP';
    default:
      return 'VARCHAR';
  }
};

function SchemaEditorContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { dataService } = useServices();
  const { startProcessing } = useProcessing();

  const fileId = searchParams?.get('file_id') ?? '';
  const fileName = searchParams?.get('file_name') ?? 'Uploaded file';

  const [fields, setFields] = useState<EditableSchemaField[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;

    const run = async () => {
      if (!fileId) {
        setError('Missing file_id in URL');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError('');

      try {
        const result = await dataService.validateSchema(fileId);
        const inferredFields = result.columns || [];

        const nextFields: EditableSchemaField[] = inferredFields
          .map((f) => {
            const originalName = (f.name || '').trim();
            if (!originalName) return null;
            return {
              originalName,
              name: originalName,
              type: frictionlessTypeToDuckdbType(f.type),
            };
          })
          .filter((x): x is EditableSchemaField => Boolean(x));

        if (!cancelled) {
          setFields(nextFields);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Failed to infer schema');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    run();
    return () => {
      cancelled = true;
    };
  }, [dataService, fileId]);

  const updateField = (index: number, patch: Partial<EditableSchemaField>) => {
    setFields((prev) =>
      prev.map((field, i) => (i === index ? { ...field, ...patch } : field))
    );
  };

  const addField = () => {
    setFields((prev) => [
      ...prev,
      { originalName: '', name: '', type: 'VARCHAR' },
    ]);
  };

  const removeField = (index: number) => {
    setFields((prev) => prev.filter((_, i) => i !== index));
  };

  const handleCancel = () => {
    router.back();
  };

  const handleDone = async () => {
    if (!fileId) return;
    setSaving(true);
    setError('');

    try {
      const normalizedFields = fields.map((f) => {
        const name = f.name.trim();
        return {
          ...f,
          name: name || f.originalName,
        };
      });

      const emptyName = normalizedFields.find((f) => !f.name);
      if (emptyName) {
        setError('All columns must have a name.');
        setSaving(false);
        return;
      }

      const names = normalizedFields.map((f) => f.name.toLowerCase());
      if (new Set(names).size !== names.length) {
        setError('Column names must be unique.');
        setSaving(false);
        return;
      }

      await dataService.updateFileRegistry(fileId, {
        file_schema: {
          fields: normalizedFields,
        },
        status: 'SCHEMA_CONFIRMED',
      });

      // Build proposed_schema dict keyed by original column name for inferred fields,
      // or by user-provided name for manually-added fields
      const proposedSchema: Record<string, string> = {};
      for (const f of normalizedFields) {
        proposedSchema[f.originalName || f.name] = f.type;
      }
      await dataService.processFile(fileId, proposedSchema);

      // Start global SSE monitoring — toast will appear on any page
      startProcessing(fileId);
      router.push('/homescreen');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to save schema');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-white flex items-center justify-center p-6">
      <main className="w-full max-w-3xl">
        <div className="border-[3px] border-slate-500 rounded-lg bg-white p-10">
          <h1 className="text-3xl font-semibold text-slate-900 mb-10">
            {fileName}
          </h1>

          <h2 className="text-xl font-semibold text-slate-900">File Details</h2>
          <p className="text-slate-500 mt-2 mb-8">
            {fields.length > 0
              ? 'Here are the columns we detected:'
              : 'No columns were detected. You can add them manually below.'}
          </p>

          <div className="border-t border-slate-200 pt-6">
            <div className="grid grid-cols-[1fr_1fr_auto] gap-4 text-slate-900 font-medium mb-4">
              <div>Name</div>
              <div>Type</div>
              <div className="w-8" />
            </div>

            {loading ? (
              <div className="py-8 text-slate-500">Loading columns…</div>
            ) : (
              <>
                {fields.length > 0 && (
                  <div className="space-y-4">
                    {fields.map((field, index) => (
                      <div
                        key={index}
                        className="grid grid-cols-[1fr_1fr_auto] gap-4 items-center"
                      >
                        <div className="relative">
                          <input
                            value={field.name}
                            onChange={(e) =>
                              updateField(index, { name: e.target.value })
                            }
                            placeholder="Column name"
                            className="w-full border-[2px] border-slate-500 rounded px-4 py-2 pr-10 text-slate-900"
                            aria-label={`Column name for ${field.originalName || `column ${index + 1}`}`}
                          />
                          <div className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-700 pointer-events-none">
                            <svg
                              width="18"
                              height="18"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <path d="M12 20h9" />
                              <path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4Z" />
                            </svg>
                          </div>
                        </div>

                        <div>
                          <select
                            value={field.type}
                            onChange={(e) =>
                              updateField(index, { type: e.target.value })
                            }
                            className="w-full border-[2px] border-slate-500 rounded px-4 py-2 text-slate-900 bg-white"
                            aria-label={`Column type for ${field.originalName || `column ${index + 1}`}`}
                          >
                            {TYPE_OPTIONS.map((opt) => (
                              <option key={opt.value} value={opt.value}>
                                {opt.label}
                              </option>
                            ))}
                          </select>
                        </div>

                        <button
                          onClick={() => removeField(index)}
                          disabled={saving}
                          className="w-8 h-8 flex items-center justify-center text-slate-400 hover:text-red-500 disabled:opacity-50 transition-colors"
                          aria-label="Remove column"
                        >
                          <svg
                            width="18"
                            height="18"
                            viewBox="0 0 24 24"
                            fill="none"
                            stroke="currentColor"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          >
                            <line x1="18" y1="6" x2="6" y2="18" />
                            <line x1="6" y1="6" x2="18" y2="18" />
                          </svg>
                        </button>
                      </div>
                    ))}
                  </div>
                )}

                <button
                  onClick={addField}
                  disabled={saving}
                  className="mt-4 px-4 py-2 text-sm border border-dashed border-slate-400 rounded text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition-colors"
                >
                  + Add column
                </button>
              </>
            )}

            {error && (
              <div className="mt-6 text-red-600 text-sm font-medium">
                {error}
              </div>
            )}
          </div>

          <div className="flex justify-end gap-4 mt-12">
            <button
              onClick={handleCancel}
              disabled={saving}
              className="px-10 py-2.5 bg-white border border-slate-500 rounded text-slate-800 font-medium hover:bg-slate-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleDone}
              disabled={loading || saving || fields.length === 0}
              className="px-10 py-2.5 bg-[#CFE8F8] border border-slate-500 rounded text-slate-900 font-medium hover:bg-[#badcf5] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {saving ? 'Saving…' : 'Done'}
            </button>
          </div>
        </div>
      </main>
    </div>
  );
}

export default function SchemaEditorPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen flex items-center justify-center p-6 text-slate-500">
          Loading editor...
        </div>
      }
    >
      <SchemaEditorContent />
    </Suspense>
  );
}
