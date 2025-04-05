"use client";

import React, { useState, useEffect } from 'react';
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
import { Textarea } from "@/components/ui/textarea";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Loader2, XCircle, Search } from 'lucide-react';
import { useConnection } from "@/context/ConnectionContext";

interface RetrievalResult {
  success: boolean;
  message?: string; // Error message
  results?: Array<{ content: string; metadata: Record<string, unknown>; score?: number }>; // Array of retrieved documents
}

export function RetrievalTestingCard() {
  const [tableName, setTableName] = useState('');
  const [query, setQuery] = useState('');
  const [kValue, setKValue] = useState<number>(3);
  const [threshold, setThreshold] = useState<number>(0.5);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<RetrievalResult | null>(null);
  const { connectionString, isConnected, selectedTableName, apiType, apiKey } = useConnection();

  // Effect to update local tableName when context changes
  useEffect(() => {
    if (selectedTableName) {
      setTableName(selectedTableName);
    }
    // Optional: Clear input if selectedTableName becomes null?
    // else {
    //   setTableName(''); 
    // }
  }, [selectedTableName]);

  // TODO: Fetch available tables for the select dropdown?

  const handleExecuteQuery = async () => {
    if (!isFormValid()) return;
    
    setIsLoading(true);
    setResult(null);
    
    console.log("Sending request to /api/test_retrieval");

    try {
      // Construct API URL using environment variable
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || ''; // Default to relative path if not set
      const apiUrl = `${apiBaseUrl}/api/test_retrieval`;
      console.log("Fetching from:", apiUrl); 
      
      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          connection_string: connectionString,
          table_name: tableName,
          query: query,
          k: kValue,
          threshold: threshold,
          api_key_type: apiType,
          api_key: apiKey,
        }),
      });

      const data: RetrievalResult = await response.json();
      
      if (!response.ok) {
         setResult({ 
           success: false, 
           message: data?.message || `Request failed with status: ${response.status}`
         });
      } else {
        // Ensure results field is always an array, even if empty or missing from backend response
        setResult({ 
           success: data.success, 
           message: data.message, // Include message even on success if present (e.g., partial success info?)
           results: Array.isArray(data.results) ? data.results : [] 
        });
      }
    } catch (error) {
      console.error("Failed to execute retrieval test:", error);
      setResult({ 
        success: false, 
        message: error instanceof Error ? error.message : "An unknown error occurred while contacting the server."
      });
    }
    
    setIsLoading(false);
  };
  
  const isFormValid = (): boolean => {
     const valid = isConnected && !!tableName && !!query && kValue > 0 && threshold >= 0 && threshold <= 1 && !!apiType && !!apiKey;
      if (!valid) {
        console.log('isFormValid check failed (Retrieval):', {
            isConnected,
            tableName: !!tableName,
            query: !!query,
            kValue,
            threshold,
            apiType: !!apiType,
            apiKey: !!apiKey,
        });
    }
     return valid;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Retrieval Testing</CardTitle>
        <CardDescription>Test vector retrieval effectiveness from a specified table.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Row 1: Table Name, Query */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="retrieval-table-name">Select Vector Table</Label>
            <Input id="retrieval-table-name" placeholder="TiDB vector table used for providing vector queries." value={tableName} onChange={(e) => setTableName(e.target.value)} disabled={isLoading} />
          </div>
           <div className="space-y-2 md:col-span-2">
             <Label htmlFor="retrieval-query">Query</Label>
             <Textarea id="retrieval-query" placeholder="Enter your search query..." value={query} onChange={(e) => setQuery(e.target.value)} disabled={isLoading} rows={3} />
           </div>
        </div>

         {/* Row 2: Parameters (K, Threshold) */}
         <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
           <div className="space-y-2">
             <Label htmlFor="retrieval-k">K (Top Results)</Label>
             <Input id="retrieval-k" type="number" min="1" value={kValue} onChange={(e) => setKValue(parseInt(e.target.value) || 1)} disabled={isLoading} />
           </div>
           <div className="space-y-2">
             <Label htmlFor="retrieval-threshold">Score Threshold</Label>
             <Input id="retrieval-threshold" type="number" min="0" max="1" step="0.05" value={threshold} onChange={(e) => setThreshold(parseFloat(e.target.value) || 0)} disabled={isLoading} />
           </div>
         </div>
        
        {/* Results Area */}
        {isLoading && (
             <div className="flex items-center text-sm text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Executing query...
             </div>
        )}
         {result && !isLoading && (
            <div className="space-y-4">
              <h4 className="font-medium">Results:</h4>
              {!result.success && (
                  <Alert variant='destructive'>
                    <XCircle className="h-4 w-4" />
                    <AlertTitle>Error</AlertTitle>
                    <AlertDescription>{result.message || 'An unknown error occurred.'}</AlertDescription>
                  </Alert>
              )}
              {result.success && (!result.results || result.results.length === 0) && (
                  <Alert variant='default'>
                    <Search className="h-4 w-4" />
                    <AlertTitle>No Results</AlertTitle>
                    <AlertDescription>Your query did not return any results matching the criteria.</AlertDescription>
                  </Alert>
              )}
              {result.success && result.results && result.results.length > 0 && (
                 <div className="space-y-3 border rounded-md p-4 max-h-80 overflow-y-auto bg-gray-50 dark:bg-gray-800/50">
                    {result.results.map((doc, index) => (
                      <div key={index} className="p-3 border-b last:border-b-0">
                        {doc.score !== undefined && (
                           <p className="text-xs font-semibold text-blue-600 dark:text-blue-400 mb-1">Score: {doc.score.toFixed(4)}</p>
                        )}
                        <p className="text-sm mb-1 whitespace-pre-wrap">{doc.content}</p>
                        <p className="text-xs text-muted-foreground">Metadata: {JSON.stringify(doc.metadata)}</p>
                      </div>
                    ))}
                 </div>
              )}
            </div>
         )}
      </CardContent>
      <CardFooter>
        <Button onClick={handleExecuteQuery} disabled={!isConnected || isLoading || !isFormValid()}>
          {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Execute Query
        </Button>
      </CardFooter>
    </Card>
  );
} 