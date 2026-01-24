// src/app/login/page.tsx
'use client';

import { Suspense, useActionState, use } from 'react';
import { signInAction } from '../auth/actions';

function LoginForm({ message }: { message?: string }) {
  const [state, formAction, isPending] = useActionState(
    async (prevState: { error?: string } | null, formData: FormData) => {
      return await signInAction(formData);
    },
    null
  );

  return (
    <div className="w-full max-w-md">
      {/* Logo & Title */}
      <div className="text-center mb-8">
        <div className="w-16 h-16 mx-auto rounded-2xl bg-gradient-to-br from-[#1c66bb] to-[#0d4a8f] flex items-center justify-center shadow-lg shadow-blue-500/20 mb-4">
          <span className="text-white font-bold text-2xl">T</span>
        </div>
        <h1 className="text-2xl font-semibold text-slate-800">
          Texas Hearing Institute
        </h1>
        <p className="text-slate-500 mt-1">Data Warehouse Portal</p>
      </div>

      {/* Success Message from Signup */}
      {message && (
        <div className="mb-6 bg-cyan-50 text-cyan-700 text-sm px-4 py-3 rounded-xl border border-cyan-200">
          {message}
        </div>
      )}

      {/* Login Form */}
      <form
        action={formAction}
        className="bg-white rounded-2xl shadow-xl shadow-slate-200/50 border border-slate-200 p-8 space-y-5"
      >
        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Email
          </label>
          <input
            type="email"
            name="email"
            placeholder="you@texashearing.org"
            required
            className="w-full px-4 py-3 text-slate-700 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#1c66bb]/30 focus:border-[#1c66bb] focus:bg-white transition-all duration-200"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-slate-700 mb-2">
            Password
          </label>
          <input
            type="password"
            name="password"
            placeholder="••••••••"
            required
            className="w-full px-4 py-3 text-slate-700 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-[#1c66bb]/30 focus:border-[#1c66bb] focus:bg-white transition-all duration-200"
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
          className="w-full py-3 px-4 bg-gradient-to-r from-[#1c66bb] to-[#0d4a8f] text-white font-medium rounded-xl hover:shadow-lg hover:shadow-blue-500/25 transition-all duration-200 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isPending ? (
            <span className="flex items-center justify-center gap-2">
              <span className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin"></span>
              Signing in...
            </span>
          ) : (
            'Sign In'
          )}
        </button>

        <p className="text-center text-sm text-slate-500">
          Don&apos;t have an account?{' '}
          <a
            href="/signup"
            className="text-[#1c66bb] hover:underline font-medium"
          >
            Create one
          </a>
        </p>
      </form>
    </div>
  );
}

export default function LoginPage(props: {
  searchParams: Promise<{ [key: string]: string | string[] | undefined }>;
}) {
  const searchParams = use(props.searchParams);
  const message =
    typeof searchParams.message === 'string' ? searchParams.message : undefined;

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-cyan-50 to-blue-50 flex items-center justify-center p-4">
      <Suspense fallback={<div>Loading...</div>}>
        <LoginForm message={message} />
      </Suspense>
    </div>
  );
}
