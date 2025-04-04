"use client";

import React, { useState } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { CheckCircle, XCircle, Loader2 } from 'lucide-react'; // Icons for status
import { useConnection } from "@/context/ConnectionContext"; // Import the context hook

type ConnectionStatus = {
  success: boolean;
  message: string;
} | null;

export function DatabaseConnectionCard() {
  const [connectionStringInput, setConnectionStringInput] = useState(''); // Renamed state
  const [status, setStatus] = useState<ConnectionStatus>(null);
  const [isLoading, setIsLoading] = useState(false);
  const { setConnection } = useConnection(); // Get the setter function from context

  const handleTestConnection = async () => {
    setIsLoading(true);
    setStatus(null);
    setConnection(connectionStringInput, false); // Clear previous connection status in context immediately
    
    try {
      // Construct API URL using environment variable
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const apiUrl = `${apiBaseUrl}/api/ping_tidb`;
      console.log("Fetching from:", apiUrl);
      
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ connection_string: connectionStringInput }), // Use local state input
      });

      const data: ConnectionStatus & { message: string } = await response.json();

      if (!response.ok) {
        setStatus({ 
          success: false, 
          message: data?.message || `Request failed with status: ${response.status}` 
        });
        setConnection(connectionStringInput, false); // Update context: connection failed
      } else {
        setStatus({ 
          success: data.success, 
          message: data.message 
        });
        // Update context only if backend confirms success
        setConnection(connectionStringInput, data.success); 
      }
    } catch (error) {
      console.error("Failed to test connection:", error);
      setStatus({ 
        success: false, 
        message: error instanceof Error ? error.message : "An unknown error occurred while contacting the server."
      });
      setConnection(connectionStringInput, false); // Update context: connection failed
    }

    setIsLoading(false);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Database Connection</CardTitle>
        <CardDescription>Configure and test your TiDB connection.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="connection-string">TiDB Connection String</Label>
            <Input 
              id="connection-string" 
              type="password" 
              placeholder="mysql+pymysql://user:pass@host:port/db" 
              value={connectionStringInput} // Bind to local input state
              onChange={(e) => setConnectionStringInput(e.target.value)} // Update local input state
              disabled={isLoading}
            />
          </div>
          {/* Status message display */}
          {isLoading && (
            <div className="flex items-center text-sm text-muted-foreground">
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              Testing connection...
            </div>
          )}
          {status && !isLoading && (
            <Alert variant={status.success ? 'default' : 'destructive'}>
              {status.success ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
              <AlertTitle>{status.success ? 'Success' : 'Error'}</AlertTitle>
              <AlertDescription>{status.message}</AlertDescription>
            </Alert>
          )}
        </div>
      </CardContent>
      <CardFooter>
        <Button 
          onClick={handleTestConnection} 
          disabled={isLoading || !connectionStringInput} // Disable based on local input
          className="disabled:opacity-70 disabled:cursor-not-allowed"
        >
          {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Test Connection
        </Button>
      </CardFooter>
    </Card>
  );
} 