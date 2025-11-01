// src/app/instruments/page.tsx

import { createClient } from "../../utils/supabase/server";
import { redirect } from "next/navigation";

export default async function InstrumentsPage() {
  const supabase = await createClient();

  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    redirect("/login");
  }

  let instruments = [];
  let tableError = null;

  try {
    const { data, error } = await supabase.from("instruments").select("*");
    if (error) {
      console.error("Error fetching instruments:", error);
      tableError = error;
    } else {
      instruments = data || [];
    }
  } catch (error) {
    console.error("Failed to fetch instruments:", error);
    tableError = error;
  }

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Welcome, {session.user.email}!</h1>
      <h2 className="text-2xl font-semibold mb-4">Available Instruments</h2>

      {tableError ? (
        <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 mb-6 rounded">
          <p className="font-bold">Error loading instruments</p>
          <p>The instruments table does not exist in the database or you don't have permission to access it.</p>
          <p className="text-sm mt-2">Error details: {tableError.message}</p>
        </div>
      ) : instruments.length > 0 ? (
        <div className="bg-white shadow overflow-hidden sm:rounded-lg">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                {instruments.length > 0 && Object.keys(instruments[0]).map((key) => (
                  <th key={key} className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    {key}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {instruments.map((instrument, index) => (
                <tr key={index}>
                  {Object.values(instrument).map((value, i) => (
                    <td key={i} className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {String(value)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="bg-blue-100 border-l-4 border-blue-500 text-blue-700 p-4 rounded">
          <p>No instruments found. The table exists but is empty.</p>
        </div>
      )}

      <form action="/auth/signout" method="post" className="mt-6">
        <button
          type="submit"
          className="bg-red-500 text-white p-2 rounded hover:bg-red-600 transition"
        >
          Sign Out
        </button>
      </form>
    </div>
  );
}