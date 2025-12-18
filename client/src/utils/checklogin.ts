import { createClient } from '@/utils/supabase/server';
import { User } from '@supabase/supabase-js';

export async function loginResult(): Promise<User | null> {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // Middleware handles authentication, but we still check for safety
  if (!user) {
    return null;
  }
  return user;
}
