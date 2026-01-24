import { createBrowserClient } from '@supabase/ssr';

export class SupabaseAuthService {
  private supabase;

  constructor() {
    this.supabase = createBrowserClient(
      process.env.NEXT_PUBLIC_SUPABASE_URL!,
      process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
    );
  }

  async getCurrentUserName(): Promise<string> {
    const {
      data: { user },
    } = await this.supabase.auth.getUser();

    if (user?.user_metadata) {
      const { first_name, last_name } = user.user_metadata;
      if (first_name && last_name) {
        return `${first_name} ${last_name}`;
      }
    }
    return user?.email || 'Unknown User';
  }
}
