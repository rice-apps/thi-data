'use client';

import { useEffect, useState, useCallback } from 'react';
import { UI } from '@/constants';

type ToastType = 'success' | 'error' | 'info' | 'warning';

type ToastProps = {
  message: string;
  type?: ToastType;
  duration?: number;
  onClose: () => void;
};

const typeStyles: Record<ToastType, { bg: string; icon: React.ReactNode }> = {
  success: {
    bg: 'bg-green-500',
    icon: (
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
          d="M5 13l4 4L19 7"
        />
      </svg>
    ),
  },
  error: {
    bg: 'bg-red-500',
    icon: (
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
          d="M6 18L18 6M6 6l12 12"
        />
      </svg>
    ),
  },
  warning: {
    bg: 'bg-amber-500',
    icon: (
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
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"
        />
      </svg>
    ),
  },
  info: {
    bg: 'bg-blue-500',
    icon: (
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
          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    ),
  },
};

export function Toast({
  message,
  type = 'info',
  duration,
  onClose,
}: ToastProps) {
  const [isVisible, setIsVisible] = useState(true);
  const effectiveDuration =
    duration ?? (type === 'error' ? UI.TOAST_ERROR_MS : UI.TOAST_SUCCESS_MS);
  const { bg, icon } = typeStyles[type];

  const handleClose = useCallback(() => {
    setIsVisible(false);
    setTimeout(onClose, 200);
  }, [onClose]);

  useEffect(() => {
    const timer = setTimeout(handleClose, effectiveDuration);
    return () => clearTimeout(timer);
  }, [effectiveDuration, handleClose]);

  return (
    <div
      className={`
        fixed top-20 right-4 z-[60]
        ${bg} text-white px-6 py-3 rounded-xl shadow-lg
        flex items-center gap-2
        transition-all duration-200
        ${isVisible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-4'}
      `}
    >
      <button
        onClick={handleClose}
        className="p-1 hover:bg-white/20 rounded-lg transition-colors flex-shrink-0"
      >
        {icon}
      </button>
      <span>{message}</span>
    </div>
  );
}

// Hook for managing toast state
type ToastState = {
  message: string;
  type: ToastType;
} | null;

export function useToast() {
  const [toast, setToast] = useState<ToastState>(null);

  const showToast = useCallback((message: string, type: ToastType = 'info') => {
    setToast({ message, type });
  }, []);

  const hideToast = useCallback(() => {
    setToast(null);
  }, []);

  const showSuccess = useCallback(
    (message: string) => showToast(message, 'success'),
    [showToast]
  );
  const showError = useCallback(
    (message: string) => showToast(message, 'error'),
    [showToast]
  );
  const showWarning = useCallback(
    (message: string) => showToast(message, 'warning'),
    [showToast]
  );
  const showInfo = useCallback(
    (message: string) => showToast(message, 'info'),
    [showToast]
  );

  return {
    toast,
    showToast,
    hideToast,
    showSuccess,
    showError,
    showWarning,
    showInfo,
  };
}
