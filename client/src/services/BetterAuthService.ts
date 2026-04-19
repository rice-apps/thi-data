import { authClient } from '@/lib/auth-client';
import type { IAuthService } from './interfaces';

export class BetterAuthService implements IAuthService {
  async getCurrentUserName(): Promise<string> {
    const { data } = await authClient.getSession();
    const user = data?.user;
    if (user?.name) return user.name;
    return user?.email || 'Unknown User';
  }

  async getCurrentUserEmail(): Promise<string | null> {
    const { data } = await authClient.getSession();
    return data?.user?.email ?? null;
  }

  async signOut(): Promise<void> {
    await authClient.signOut();
  }

  async isAuthenticated(): Promise<boolean> {
    const { data } = await authClient.getSession();
    return data?.user != null;
  }
}
