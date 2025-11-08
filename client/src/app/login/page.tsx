// src/app/login/page.tsx
"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { getSupabase } from "@/utils/supabase/client";

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);

    const supabase = getSupabase()
    const { error } = await supabase.auth.signInWithPassword({
      email,
      password,
    });

    setLoading(false);

    if (error) {
      console.log(`An error occurred: ${error.message}`);
      setError(error.message);
    } else {
      console.log("Login info correct");
      // Login successful, redirect to home page
      router.push("/");
      router.refresh(); // Refresh to update server-side session
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50">
      <form onSubmit={handleLogin} className="w-full max-w-sm p-6 bg-white rounded-2xl shadow-lg space-y-4">
        <h2 className="text-2xl font-semibold text-center">Log In</h2>

        <input
          type="email"
          placeholder="Email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="w-full p-2 border rounded"
          required
        />

        <input
          type="password"
          placeholder="Password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="w-full p-2 border rounded"
          required
        />

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700 transition"
        >
          {loading ? "Logging in..." : "Log In"}
        </button>

        <p className="text-center text-sm">
          Do not have an account?{" "}
          <a href="/signup" className="text-blue-600 hover:underline">
            Sign up
          </a>
        </p>
      </form>
    </div>
  );
}