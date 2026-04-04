'use client';

import React, {
  createContext,
  useContext,
  useCallback,
  useRef,
  useState,
} from 'react';
import { Toast } from './Toast';

function toUserFacingError(raw: string): string {
  if (raw.includes('Referenced column') && raw.includes('not found in FROM clause')) {
    const match = raw.match(/Referenced column "([^"]+)"/);
    const col = match ? ` "${match[1]}"` : '';
    return `Column${col} not found in the file. Please go back and re-verify your column selection.`;
  }
  return 'Processing failed. Please try uploading again.';
}

type ProcessingContextValue = {
  startProcessing: (fileId: string) => void;
  lastSuccessTimestamp: number | null;
};

const ProcessingContext = createContext<ProcessingContextValue | null>(null);

type ToastState = {
  message: string;
  type: 'success' | 'error';
} | null;

export function ProcessingProvider({
  children,
}: {
  children: React.ReactNode;
}) {
  const eventSourceRef = useRef<EventSource | null>(null);
  const [toast, setToast] = useState<ToastState>(null);
  const [lastSuccessTimestamp, setLastSuccessTimestamp] = useState<
    number | null
  >(null);

  const startProcessing = useCallback((fileId: string) => {
    // Close any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }

    const baseUrl =
      process.env.NEXT_PUBLIC_BACKEND_URL || 'http://localhost:8000';
    const streamUrl = `${baseUrl}/api/events/stream?file_id=${encodeURIComponent(fileId)}`;
    const es = new EventSource(streamUrl);
    eventSourceRef.current = es;

    const cleanup = () => {
      es.close();
      if (eventSourceRef.current === es) {
        eventSourceRef.current = null;
      }
    };

    es.addEventListener('celery_success', () => {
      setToast({ message: 'Your file has been processed!', type: 'success' });
      setLastSuccessTimestamp(Date.now());
      cleanup();
    });

    es.addEventListener('celery_failed', (event: MessageEvent) => {
      let message = 'Processing failed. Please try uploading again.';
      try {
        const payload = JSON.parse(event.data || '{}') as { error?: string };
        if (payload.error) {
          message = toUserFacingError(payload.error);
        }
      } catch {
        // use default message
      }
      setToast({ message, type: 'error' });
      cleanup();
    });

    es.onerror = () => {
      // SSE reconnects automatically; don't surface transient errors
    };
  }, []);

  return (
    <ProcessingContext.Provider
      value={{ startProcessing, lastSuccessTimestamp }}
    >
      {children}
      {toast && (
        <Toast
          message={toast.message}
          type={toast.type}
          onClose={() => setToast(null)}
        />
      )}
    </ProcessingContext.Provider>
  );
}

export function useProcessing(): ProcessingContextValue {
  const context = useContext(ProcessingContext);
  if (!context) {
    throw new Error('useProcessing must be used within a ProcessingProvider');
  }
  return context;
}
