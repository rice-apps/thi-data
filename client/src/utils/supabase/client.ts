import { createBrowserClient } from '@supabase/ssr';

export function getSupabase() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}

export async function getCurrentUserName(): Promise<string> {
  const supabase = getSupabase();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user?.user_metadata) {
    const { first_name, last_name } = user.user_metadata;
    if (first_name && last_name) {
      return `${first_name} ${last_name}`;
    }
  }
  return user?.email || 'Unknown User';
}

export default getSupabase;
