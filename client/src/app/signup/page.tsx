"use client";

import { useState } from "react";
import { getSupabase } from "../../utils/supabase/client";
import { useRouter } from "next/navigation";

export default function SignupPage() {
  const router = useRouter();
  const [form, setForm] = useState({
    firstName: "",
    lastName: "",
    email: "",
    password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!form.email.endsWith("@texashearing.org")) {
      setError("Please use your @texashearing.org email address.");
      return;
    }

    setLoading(true);
    const supabase = getSupabase()
    const { error } = await supabase.auth.signUp({
      email: form.email,
      password: form.password,
      options: {
        data: {
          first_name: form.firstName,
          last_name: form.lastName,
        },
      },
    });
    setLoading(false);

    if (error) {
      setError(error.message);
    } else {
      alert("Account created! Check your email for verification.");
      router.push("/login");
    }
  };

  return (
    <div className="flex flex-col items-center justify-center min-h-screen bg-gray-50">
      <form
        onSubmit={handleSignup}
        className="w-full max-w-sm p-6 bg-white rounded-2xl shadow-lg space-y-4"
      >
        <h2 className="text-2xl font-semibold text-center">Create Account</h2>

        <input
          type="text"
          name="firstName"
          placeholder="First Name"
          onChange={handleChange}
          value={form.firstName}
          className="w-full p-2 border rounded"
          required
        />

        <input
          type="text"
          name="lastName"
          placeholder="Last Name"
          onChange={handleChange}
          value={form.lastName}
          className="w-full p-2 border rounded"
          required
        />

        <input
          type="email"
          name="email"
          placeholder="THI Email (@texashearing.org)"
          onChange={handleChange}
          value={form.email}
          className="w-full p-2 border rounded"
          required
        />

        <input
          type="password"
          name="password"
          placeholder="Password"
          onChange={handleChange}
          value={form.password}
          className="w-full p-2 border rounded"
          required
        />

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white p-2 rounded hover:bg-blue-700 transition"
        >
          {loading ? "Creating..." : "Create Account"}
        </button>

        <p className="text-center text-sm">
          Already have an account?{" "}
          <a href="/login" className="text-blue-600 hover:underline">
            Log in
          </a>
        </p>
      </form>
    </div>
  );
}
