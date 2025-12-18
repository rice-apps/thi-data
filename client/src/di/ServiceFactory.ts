import { AuthService } from '@/domain/AuthService';
import { DataService } from '@/domain/DataService';
import { SupabaseAuthService } from '@/infrastructure/SupabaseAuthService';
import { HttpDataService } from '@/infrastructure/HttpDataService';

export class ServiceFactory {
  static getAuthService(): AuthService {
    return new SupabaseAuthService();
  }

  static getDataService(authService?: AuthService): DataService {
    const auth = authService || this.getAuthService();
    return new HttpDataService(auth);
  }
}
