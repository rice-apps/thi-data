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
      {/* Title */}
      <div className="mb-8">
        <h1 className="text-4xl font-bold text-slate-900">Welcome Back!</h1>
        <p className="text-slate-500 mt-2 text-lg">
          Sign in to access your dashboard.
        </p>
      </div>

      {/* Success Message from Signup */}
      {message && (
        <div className="mb-6 bg-cyan-50 text-cyan-700 text-sm px-4 py-3 rounded-xl border border-cyan-200">
          {message}
        </div>
      )}

      {/* Login Form */}
      <form action={formAction} className="space-y-5">
        <div>
          <label className="block text-sm font-semibold text-slate-700 mb-1.5">
            Email
          </label>
          <input
            type="email"
            name="email"
            placeholder="Email"
            required
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
            className="w-full px-4 py-3 text-slate-700 bg-white border border-slate-300 rounded-full focus:outline-none focus:ring-2 focus:ring-[#1c3a6b]/30 focus:border-[#1c3a6b] transition-all duration-200"
          />
          <div className="text-right mt-1.5">
            <a
              href="/forgot-password"
              className="text-sm text-[#1c3a6b] hover:underline font-medium"
            >
              Forgot Password?
            </a>
          </div>
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
              Signing in...
            </span>
          ) : (
            'Sign in'
          )}
        </button>

        <p className="text-center text-sm text-slate-500 mt-2">
          Don&apos;t have an account?{' '}
          <a
            href="/signup"
            className="text-[#1c3a6b] hover:underline font-medium"
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
      <div className="bg-white rounded-3xl shadow-lg shadow-slate-200/60 p-10 w-full max-w-lg">
        <Suspense fallback={<div>Loading...</div>}>
          <LoginForm message={message} />
        </Suspense>
      </div>
    </div>
  );
}
