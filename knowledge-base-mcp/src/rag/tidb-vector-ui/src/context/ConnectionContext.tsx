"use client";

import React, { createContext, useState, useContext, ReactNode } from 'react';
import type { ApiType } from "@/lib/types";

interface ConnectionState {
  connectionString: string | null;
  isConnected: boolean;
  selectedTableName: string | null;
  apiType: ApiType | null;
  apiKey: string | null;
}

interface ConnectionContextType extends ConnectionState {
  setConnection: (connectionString: string, status: boolean) => void;
  clearConnection: () => void;
  setSelectedTable: (tableName: string | null) => void;
  setApiConfig: (apiType: ApiType | null, apiKey: string | null) => void;
}

const ConnectionContext = createContext<ConnectionContextType | undefined>(undefined);

export const ConnectionProvider = ({ children }: { children: ReactNode }) => {
  const [connectionState, setConnectionState] = useState<ConnectionState>({ 
      connectionString: null,
      isConnected: false, 
      selectedTableName: null,
      apiType: null,
      apiKey: null,
  });

  const setConnection = (connectionString: string, status: boolean) => {
    console.log('Setting connection context:', status ? connectionString : null);
    setConnectionState(prevState => ({ 
        ...prevState,
        connectionString: status ? connectionString : null, 
        isConnected: status,
        selectedTableName: status ? prevState.selectedTableName : null,
        apiType: prevState.apiType,
        apiKey: prevState.apiKey,
    }));
  };
  
  const clearConnection = () => {
      console.log('Clearing connection context');
      setConnectionState({ 
          connectionString: null, 
          isConnected: false, 
          selectedTableName: null, 
          apiType: null, 
          apiKey: null 
      });
  };

  const setSelectedTable = (tableName: string | null) => {
      console.log('Setting selected table name:', tableName);
      setConnectionState(prevState => ({ ...prevState, selectedTableName: tableName }));
  };

  const setApiConfig = (apiType: ApiType | null, apiKey: string | null) => {
      console.log('Setting API config:', apiType, apiKey ? '******' : null);
      setConnectionState(prevState => ({ ...prevState, apiType: apiType, apiKey: apiKey }));
  };

  return (
    <ConnectionContext.Provider value={{ ...connectionState, setConnection, clearConnection, setSelectedTable, setApiConfig }}>
      {children}
    </ConnectionContext.Provider>
  );
};

export const useConnection = (): ConnectionContextType => {
  const context = useContext(ConnectionContext);
  if (context === undefined) {
    throw new Error('useConnection must be used within a ConnectionProvider');
  }
  return context;
}; 