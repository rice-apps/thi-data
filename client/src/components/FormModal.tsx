'use client';

import { Modal, ModalBody, ModalFooter } from './Modal';
import { Button } from './Button';

type FormField = {
  name: string;
  label: string;
  value: string;
  required?: boolean;
  placeholder?: string;
  type?: 'text' | 'number' | 'email';
};

type FormModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSubmit: () => void;
  title: string;
  fields: FormField[];
  onChange: (name: string, value: string) => void;
  submitLabel?: string;
  cancelLabel?: string;
  loading?: boolean;
};

export function FormModal({
  isOpen,
  onClose,
  onSubmit,
  title,
  fields,
  onChange,
  submitLabel = 'Save',
  cancelLabel = 'Cancel',
  loading = false,
}: FormModalProps) {
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <Modal isOpen={isOpen} onClose={onClose} title={title} disableClose={loading}>
      <form onSubmit={handleSubmit}>
        <ModalBody className="space-y-4">
          {fields.map((field) => (
            <div key={field.name}>
              <label className="block text-sm font-medium text-slate-700 mb-1">
                {field.label}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </label>
              <input
                type={field.type || 'text'}
                value={field.value}
                onChange={(e) => onChange(field.name, e.target.value)}
                placeholder={field.placeholder || `Enter ${field.label.toLowerCase()}`}
                className={`
                  w-full px-4 py-2 text-slate-700 bg-slate-50 border rounded-xl
                  focus:outline-none focus:ring-2 focus:ring-[#1c66bb]/30 focus:border-[#1c66bb]
                  focus:bg-white transition-all duration-200
                  ${field.required && field.value.trim() === '' ? 'border-red-300' : 'border-slate-200'}
                `}
              />
            </div>
          ))}
        </ModalBody>
        <ModalFooter>
          <Button variant="ghost" onClick={onClose} disabled={loading} type="button">
            {cancelLabel}
          </Button>
          <Button variant="primary" type="submit" loading={loading}>
            {loading ? 'Saving...' : submitLabel}
          </Button>
        </ModalFooter>
      </form>
    </Modal>
  );
}
