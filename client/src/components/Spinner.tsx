import { COLORS } from '@/constants';

type SpinnerSize = 'sm' | 'md' | 'lg';

type SpinnerProps = {
  size?: SpinnerSize;
  color?: string;
  className?: string;
};

const sizeStyles: Record<SpinnerSize, string> = {
  sm: 'w-4 h-4 border-2',
  md: 'w-6 h-6 border-2',
  lg: 'w-8 h-8 border-3',
};

export function Spinner({
  size = 'md',
  color = COLORS.PRIMARY,
  className = '',
}: SpinnerProps) {
  return (
    <div
      className={`
        ${sizeStyles[size]}
        border-t-transparent rounded-full animate-spin
        ${className}
      `}
      style={{ borderColor: `${color}33`, borderTopColor: color }}
    />
  );
}
