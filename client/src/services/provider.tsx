'use client';

import React, { createContext, useContext, useMemo } from 'react';
import { ServiceFactory } from './factory';
import type { IAuthService, IDataService } from './interfaces';

type ServiceContextValue = {
  authService: IAuthService;
  dataService: IDataService;
};

const ServiceContext = createContext<ServiceContextValue | null>(null);

type ServiceProviderProps = {
  children: React.ReactNode;
  services?: Partial<ServiceContextValue>;
};

/**
 * Provider component for services.
 * Accepts optional services prop for dependency injection (useful for testing).
 */
export function ServiceProvider({ children, services }: ServiceProviderProps) {
  const contextValue = useMemo(() => {
    const authService =
      services?.authService ?? ServiceFactory.getAuthService();
    const dataService =
      services?.dataService ?? ServiceFactory.getDataService(authService);
    return { authService, dataService };
  }, [services]);

  return (
    <ServiceContext.Provider value={contextValue}>
      {children}
    </ServiceContext.Provider>
  );
}

/**
 * Hook to access both auth and data services.
 */
export function useServices(): ServiceContextValue {
  const context = useContext(ServiceContext);
  if (!context) {
    throw new Error('useServices must be used within a ServiceProvider');
  }
  return context;
}

/**
 * Convenience hook to access auth service.
 */
export function useAuthService(): IAuthService {
  const { authService } = useServices();
  return authService;
}

/**
 * Convenience hook to access data service.
 */
export function useDataService(): IDataService {
  const { dataService } = useServices();
  return dataService;
}
