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

  const { data: instruments, error } = await supabase.from("instruments").select("*");

  if (error) {
    console.error("Error fetching instruments:", error);
    return <div>Error loading instruments data.</div>;
  }

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">Welcome, {session.user.email}!</h1>
      <h2 className="text-2xl font-semibold mb-4">Available Instruments</h2>

      <pre className="bg-gray-100 p-4 rounded-lg overflow-x-auto">
        {JSON.stringify(instruments, null, 2)}
      </pre>

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