'use client';

import React, { createContext, useContext, useMemo } from 'react';
import {
  ServiceFactory,
  AuthServiceInstance,
  DataServiceInstance,
} from './factory';

type ServiceContextValue = {
  authService: AuthServiceInstance;
  dataService: DataServiceInstance;
};

const ServiceContext = createContext<ServiceContextValue | null>(null);

export function ServiceProvider({ children }: { children: React.ReactNode }) {
  const services = useMemo(() => {
    const authService = ServiceFactory.getAuthService();
    const dataService = ServiceFactory.getDataService(authService);
    return { authService, dataService };
  }, []);

  return (
    <ServiceContext.Provider value={services}>
      {children}
    </ServiceContext.Provider>
  );
}

export function useServices(): ServiceContextValue {
  const context = useContext(ServiceContext);
  if (!context) {
    throw new Error('useServices must be used within a ServiceProvider');
  }
  return context;
}
