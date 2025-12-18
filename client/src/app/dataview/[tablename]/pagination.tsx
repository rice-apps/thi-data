'use client';

import { usePathname, useSearchParams } from 'next/navigation';
import Link from 'next/link';

export default function Pagination({ totalPages }: { totalPages: number }) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentPage = Number(searchParams?.get('page')) || 1;

  const createPageURL = (pageNumber: number | string) => {
    const params = new URLSearchParams(searchParams || '');
    params.set('page', pageNumber.toString());
    return `${pathname}?${params.toString()}`;
  };

  return (
    <div className="flex gap-2 items-center">
      {/* Previous button */}
      <Link
        href={createPageURL(currentPage - 1)}
        className={`px-3 py-1 rounded ${
          currentPage <= 1
            ? 'bg-gray-200 text-gray-400 cursor-not-allowed pointer-events-none'
            : 'bg-blue-500 text-white hover:bg-blue-600'
        }`}
      >
        Previous
      </Link>

      {/* Page numbers */}
      <div className="flex gap-1">
        {Array.from({ length: totalPages }, (_, i) => i + 1).map((page) => (
          <Link
            key={page}
            href={createPageURL(page)}
            className={`px-3 py-1 rounded ${
              currentPage === page
                ? 'bg-blue-500 text-white font-bold'
                : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
            }`}
          >
            {page}
          </Link>
        ))}
      </div>

      {/* Next button */}
      <Link
        href={createPageURL(currentPage + 1)}
        className={`px-3 py-1 rounded ${
          currentPage >= totalPages
            ? 'bg-gray-200 text-gray-400 cursor-not-allowed pointer-events-none'
            : 'bg-blue-500 text-white hover:bg-blue-600'
        }`}
      >
        Next
      </Link>
    </div>
  );
}
