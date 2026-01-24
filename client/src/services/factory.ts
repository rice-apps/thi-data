import { SupabaseAuthService } from './SupabaseAuthService';
import { HttpDataService } from './HttpDataService';

export type AuthServiceInstance = InstanceType<typeof SupabaseAuthService>;
export type DataServiceInstance = InstanceType<typeof HttpDataService>;

export class ServiceFactory {
  static getAuthService(): AuthServiceInstance {
    return new SupabaseAuthService();
  }

  static getDataService(authProvider?: {
    getCurrentUserName(): Promise<string>;
  }): DataServiceInstance {
    const auth = authProvider || this.getAuthService();
    return new HttpDataService(auth);
  }
}
