"use client";

import React, { useState, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter, // Keep footer for potential save/status
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useConnection } from "@/context/ConnectionContext";
import { ApiType } from "@/lib/types";
import { CheckCircle, Loader2, XCircle } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface ValidationStatus {
  isValidating: boolean;
  isValid: boolean | null; // null = not checked, false = invalid, true = valid
  message: string | null;
}

export function ApiConfigurationCard() {
  const { apiType: contextApiType, apiKey: contextApiKey, setApiConfig } = useConnection();
  
  // Local state to manage input before saving to context
  const [localApiType, setLocalApiType] = useState<ApiType>('google');
  const [localApiKey, setLocalApiKey] = useState('');
  
  // Validation state
  const [validationStatus, setValidationStatus] = useState<ValidationStatus>({
      isValidating: false,
      isValid: null,
      message: null
  });
  const [isSaved, setIsSaved] = useState(false);

  // Sync local state with context on initial load or context change
  useEffect(() => {
    setLocalApiType(contextApiType ?? 'google');
    setLocalApiKey(contextApiKey ?? '');
    setValidationStatus(prev => ({ ...prev, isValid: !!contextApiType && !!contextApiKey, message: null }));
  }, [contextApiType, contextApiKey]);

  // Reset validation status when inputs change
  useEffect(() => {
    setValidationStatus({
        isValidating: false,
        isValid: null,
        message: null
    });
    setIsSaved(false);
  }, [localApiType, localApiKey]);

  const handleSaveConfig = async () => {
    if (!localApiType || !localApiKey) return;

    setValidationStatus({ isValidating: true, isValid: null, message: null });
    setIsSaved(false);
    
    try {
        // Construct API URL using environment variable
        const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
        const apiUrl = `${apiBaseUrl}/api/validate_api_key`;
        console.log("Fetching from:", apiUrl);
        
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ api_key_type: localApiType, api_key: localApiKey })
        });
        
        const result = await response.json();
        
        if (response.ok && result.success) {
            // Validation successful - update context
            setApiConfig(localApiType, localApiKey);
            setValidationStatus({ isValidating: false, isValid: true, message: result.message || "API Key validated successfully." });
            setIsSaved(true);
            setTimeout(() => setIsSaved(false), 2500);
        } else {
            // Validation failed
            setApiConfig(null, null);
            setValidationStatus({ isValidating: false, isValid: false, message: result.message || "Validation failed. Please check key and type." });
        }

    } catch (error) {
        console.error("API Key validation error:", error);
        setApiConfig(null, null);
        setValidationStatus({ 
            isValidating: false, 
            isValid: false, 
            message: error instanceof Error ? error.message : "An unexpected error occurred during validation."
        });
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>API Configuration</CardTitle>
        <CardDescription>Select your embedding provider and enter the API key. This will be used for processing and retrieval.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
           <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                    <Label htmlFor="global-api-type">Embedding API</Label>
                    <Select value={localApiType} onValueChange={(value: ApiType) => { setLocalApiType(value); setIsSaved(false); }} >
                      <SelectTrigger id="global-api-type">
                        <SelectValue placeholder="Select API Provider" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="openai">OpenAI</SelectItem>
                        <SelectItem value="google">Google AI</SelectItem>
                      </SelectContent>
                    </Select>
                </div>
                <div className="space-y-2">
                    <Label htmlFor="global-api-key">API Key</Label>
                    <Input id="global-api-key" type="password" placeholder="Enter your API key" value={localApiKey} onChange={(e) => { setLocalApiKey(e.target.value); setIsSaved(false); }} />
                </div>
            </div>
            <div>
                {validationStatus.isValidating && (
                    <div className="flex items-center text-sm text-muted-foreground">
                        <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                        Validating API Key...
                    </div>
                )}
                {validationStatus.message && !validationStatus.isValidating && (
                     <Alert variant={validationStatus.isValid === false ? 'destructive' : 'default'} className="mt-2">
                        {validationStatus.isValid === false ? <XCircle className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
                        <AlertTitle>{validationStatus.isValid === false ? 'Validation Failed' : 'Validation Info'}</AlertTitle>
                        <AlertDescription>{validationStatus.message}</AlertDescription>
                    </Alert>
                )}
            </div>
      </CardContent>
      <CardFooter className="flex justify-between items-center">
          <Button 
              onClick={handleSaveConfig} 
              disabled={!localApiKey || !localApiType || validationStatus.isValidating}
          >
              {validationStatus.isValidating ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
              Validate & Save API Config
          </Button>
          {isSaved && !validationStatus.isValidating && (
              <div className="flex items-center text-sm text-green-600 dark:text-green-400">
                  <CheckCircle className="h-4 w-4 mr-1" /> Saved!
              </div>
          )}
      </CardFooter>
    </Card>
  );
} 