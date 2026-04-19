import { BetterAuthService } from './BetterAuthService';
import { HttpDataService } from './HttpDataService';
import type { IAuthService, IDataService, AuthProvider } from './interfaces';

export type AuthServiceInstance = InstanceType<typeof BetterAuthService>;
export type DataServiceInstance = InstanceType<typeof HttpDataService>;

// Singleton instances cache
let authServiceInstance: IAuthService | null = null;
let dataServiceInstance: IDataService | null = null;

// Custom implementations for dependency injection
let customAuthService: IAuthService | null = null;
let customDataService: IDataService | null = null;

export class ServiceFactory {
  /**
   * Get the auth service singleton.
   * Returns injected service if set, otherwise creates default.
   */
  static getAuthService(): IAuthService {
    if (customAuthService) {
      return customAuthService;
    }
    if (!authServiceInstance) {
      authServiceInstance = new BetterAuthService();
    }
    return authServiceInstance;
  }

  /**
   * Get the data service singleton.
   * Returns injected service if set, otherwise creates default.
   */
  static getDataService(authProvider?: AuthProvider): IDataService {
    if (customDataService) {
      return customDataService;
    }
    if (!dataServiceInstance) {
      const auth = authProvider || this.getAuthService();
      dataServiceInstance = new HttpDataService(auth);
    }
    return dataServiceInstance;
  }

  /**
   * Inject custom service implementations (useful for testing).
   */
  static inject(services: {
    authService?: IAuthService;
    dataService?: IDataService;
  }): void {
    if (services.authService) {
      customAuthService = services.authService;
    }
    if (services.dataService) {
      customDataService = services.dataService;
    }
  }

  /**
   * Reset all singletons and custom implementations.
   * Useful for test cleanup.
   */
  static reset(): void {
    authServiceInstance = null;
    dataServiceInstance = null;
    customAuthService = null;
    customDataService = null;
  }
}
