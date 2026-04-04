// src/app/signup/page.tsx
'use client';

import { useActionState, useState, useEffect } from 'react';
import { signUpAction } from '../auth/actions';

export default function SignupPage() {
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  const [state, formAction, isPending] = useActionState(
    async (
      prevState: {
        error?: string;
        values?: {
          firstName: string;
          lastName: string;
          email: string;
          password: string;
        };
      } | null,
      formData: FormData
    ) => {
      return await signUpAction(formData);
    },
    null
  );

  useEffect(() => {
    if (state?.values) {
      setFirstName(state.values.firstName);
      setLastName(state.values.lastName);
      setEmail(state.values.email);
      setPassword(state.values.password);
    }
  }, [state]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-3xl shadow-lg shadow-slate-200/60 p-10 w-full max-w-lg">
        <div className="w-full max-w-md">
          {/* Title */}
          <div className="mb-8">
            <h1 className="text-4xl font-bold text-slate-900">
              Create Account
            </h1>
            <p className="text-slate-500 mt-2 text-lg">
              Join Texas Hearing Institute.
            </p>
          </div>

          {/* Signup Form */}
          <form action={formAction} className="space-y-5">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                  First Name
                </label>
                <input
                  type="text"
                  name="firstName"
                  placeholder="First Name"
                  required
                  value={firstName}
                  onChange={(e) => setFirstName(e.target.value)}
                  className="w-full px-4 py-3 text-slate-700 bg-white border border-slate-300 rounded-full focus:outline-none focus:ring-2 focus:ring-[#1c3a6b]/30 focus:border-[#1c3a6b] transition-all duration-200"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                  Last Name
                </label>
                <input
                  type="text"
                  name="lastName"
                  placeholder="Last Name"
                  required
                  value={lastName}
                  onChange={(e) => setLastName(e.target.value)}
                  className="w-full px-4 py-3 text-slate-700 bg-white border border-slate-300 rounded-full focus:outline-none focus:ring-2 focus:ring-[#1c3a6b]/30 focus:border-[#1c3a6b] transition-all duration-200"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                Email
              </label>
              <input
                type="email"
                name="email"
                placeholder="Email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full px-4 py-3 text-slate-700 bg-white border border-slate-300 rounded-full focus:outline-none focus:ring-2 focus:ring-[#1c3a6b]/30 focus:border-[#1c3a6b] transition-all duration-200"
              />
            </div>

            <div>
              <label className="block text-sm font-semibold text-slate-700 mb-1.5">
                Password
              </label>
              <input
                type="password"
                name="password"
                placeholder="Password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 text-slate-700 bg-white border border-slate-300 rounded-full focus:outline-none focus:ring-2 focus:ring-[#1c3a6b]/30 focus:border-[#1c3a6b] transition-all duration-200"
              />
            </div>

            {state?.error && (
              <div className="bg-red-50 text-red-600 text-sm px-4 py-3 rounded-xl border border-red-200">
                {state.error}
              </div>
            )}

            <button
              type="submit"
              disabled={isPending}
              className="w-full py-3 px-4 bg-[#1c3a6b] text-white font-medium rounded-full hover:bg-[#162e55] transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isPending ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
                  Creating account...
                </span>
              ) : (
                'Create Account'
              )}
            </button>

            <p className="text-center text-sm text-slate-500 mt-2">
              Already have an account?{' '}
              <a
                href="/login"
                className="text-[#1c3a6b] hover:underline font-medium"
              >
                Sign in
              </a>
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
