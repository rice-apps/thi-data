import { createAuthClient } from 'better-auth/react';
import { BETTER_AUTH_BASE_PATH } from '@/lib/auth-path';

export const authClient = createAuthClient({
  basePath: BETTER_AUTH_BASE_PATH,
  baseURL: process.env.NEXT_PUBLIC_BETTER_AUTH_URL,
});

export const { signIn, signUp, signOut, useSession, getSession } = authClient;
