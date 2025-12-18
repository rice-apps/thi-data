'use client';

import React, { createContext, useContext, useMemo } from 'react';
import { AuthService } from '@/domain/AuthService';
import { DataService } from '@/domain/DataService';
import { ServiceFactory } from '@/di/ServiceFactory';

interface ServiceContextValue {
  authService: AuthService;
  dataService: DataService;
}

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

export function useServices() {
  const context = useContext(ServiceContext);
  if (!context) {
    throw new Error('useServices must be used within a ServiceProvider');
  }
  return context;
}
