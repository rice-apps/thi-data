// Factory and Provider
export { ServiceFactory } from './factory';
export {
  ServiceProvider,
  useServices,
  useAuthService,
  useDataService,
} from './provider';

// Types
export type { AuthServiceInstance, DataServiceInstance } from './factory';
export type { IAuthService, IDataService, AuthProvider } from './interfaces';

// Error classes and utilities
export {
  ApiError,
  NetworkError,
  ValidationError,
  getErrorMessage,
} from './errors';

// HTTP Client
export { HttpClient } from './HttpClient';
export type { HttpClientConfig, RequestOptions } from './HttpClient';
