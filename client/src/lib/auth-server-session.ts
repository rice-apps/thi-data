import 'server-only';

import { headers } from 'next/headers';
import { auth } from '@/lib/auth';

/** For RSC / Route Handlers: session from cookies + DB. Do not use authClient here — it HTTP-fetches and breaks in Docker (public BETTER_AUTH_URL is not reachable from inside the frontend container). */
export async function getSessionUserForApi() {
  const session = await auth.api.getSession({ headers: await headers() });
  return session?.user ?? null;
}
