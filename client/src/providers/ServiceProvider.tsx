'use client';

import React, { createContext, useContext, useMemo } from 'react';
import { AuthService } from '@/services/AuthService';
import { DataService } from '@/services/DataService';
import { SupabaseAuthService } from '@/services/SupabaseAuthService';
import { HttpDataService } from '@/services/HttpDataService';

interface ServiceContextValue {
  authService: AuthService;
  dataService: DataService;
}

const ServiceContext = createContext<ServiceContextValue | null>(null);

export function ServiceProvider({ children }: { children: React.ReactNode }) {
  const services = useMemo(() => {
    const authService = new SupabaseAuthService();
    const dataService = new HttpDataService(authService);

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
