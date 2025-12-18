'use client';

import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { useSearchParams } from 'next/navigation';

type SearchFormProps = {
  tablename: string;
  headers: string[];
  initialColumn?: string;
  initialSearch?: string;
};

export default function SearchForm({
  tablename,
  headers,
  initialColumn,
  initialSearch,
}: SearchFormProps) {
  const router = useRouter();
  const [selectedColumn, setSelectedColumn] = useState(
    initialColumn || headers[0] || ''
  );
  const [searchText, setSearchText] = useState(initialSearch || '');
  const searchParams = useSearchParams();

  // This runs when column changes
  const handleColumnChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newColumn = e.target.value;
    setSelectedColumn(newColumn);

    // Optional: Clear search when switching columns
    setSearchText('');
  };

  // This runs when search input changes
  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const params = new URLSearchParams(searchParams || '');
    params.set('page', '1');
    setSearchText(e.target.value);
    console.log(`Search text: ${e.target.value}`);
  };

  // This runs when form submits
  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault(); // Prevent default HTML form submission

    if (!searchText.trim()) {
      router.push(`/dataview/${tablename}`);
      return;
    }

    router.push(
      `/dataview/${tablename}?column=${selectedColumn}&search=${encodeURIComponent(searchText)}`
    );
  };

  // This runs when Clear is clicked
  const handleClear = () => {
    setSelectedColumn(headers[0] || '');
    setSearchText('');
    router.push(`/dataview/${tablename}`);
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2 items-center">
      <select
        name="column"
        value={selectedColumn}
        onChange={handleColumnChange}
        className="h-8 px-2 text-sm rounded bg-gray-50 focus:ring-1 focus:ring-blue-500 outline-none"
      >
        {headers.map((header) => (
          <option key={header} value={header}>
            {header}
          </option>
        ))}
      </select>

      <input
        type="text"
        name="search"
        value={searchText}
        onChange={handleSearchChange}
        placeholder="Search..."
        className="h-8 w-48 px-2 text-sm rounded focus:ring-1 focus:ring-blue-500 outline-none"
      />

      <button
        type="submit"
        className="h-8 px-3 text-xs font-medium bg-blue-600 text-white rounded hover:bg-blue-700 transition"
      >
        Search
      </button>

      {(searchText || initialSearch || initialColumn) && (
        <button
          type="button"
          onClick={handleClear}
          className="h-8 px-3 text-xs font-medium text-gray-500 underline"
        >
          Clear
        </button>
      )}
    </form>
  );
}
