'use client';

import { Modal, ModalBody, ModalFooter } from './Modal';
import { Button } from './Button';

type ConfirmModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'primary';
  loading?: boolean;
};

export function ConfirmModal({
  isOpen,
  onClose,
  onConfirm,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'danger',
  loading = false,
}: ConfirmModalProps) {
  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      disableClose={loading}
      className="max-w-sm"
    >
      <ModalBody className="text-center py-6">
        <h3 className="text-lg font-semibold text-slate-800 mb-2">{title}</h3>
        <p className="text-slate-500">{message}</p>
      </ModalBody>
      <ModalFooter className="justify-center">
        <Button variant="ghost" onClick={onClose} disabled={loading}>
          {cancelLabel}
        </Button>
        <Button variant={variant} onClick={onConfirm} loading={loading}>
          {loading ? `${confirmLabel.replace(/e$/, '')}ing...` : confirmLabel}
        </Button>
      </ModalFooter>
    </Modal>
  );
}
