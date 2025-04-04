"use client";

import React, { useState, useEffect, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Trash2, Loader2, XCircle, RefreshCw, CornerUpRight } from 'lucide-react';
import { Dialog, DialogTrigger, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter, DialogClose } from "@/components/ui/dialog";
import { useConnection } from "@/context/ConnectionContext"; // Import context hook
// TODO: Potentially add Dialog for delete confirmation

interface TableInfo {
  name: string;
  // Add other relevant table info if needed
}

export function TableManagementCard() {
  const [tables, setTables] = useState<TableInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState<string | null>(null); // Store name of table being deleted
  const [tableToDelete, setTableToDelete] = useState<string | null>(null); // For confirmation dialog
  const { connectionString, isConnected, setSelectedTable, selectedTableName } = useConnection(); // Use context and get setSelectedTable and selectedTableName

  // Function to fetch tables, wrapped in useCallback
  const fetchTables = useCallback(async () => {
    if (!isConnected || !connectionString) {
       setError("Database connection not established or invalid.");
       setTables([]);
       setIsLoading(false);
       return;
    }
    
    setIsLoading(true);
    setError(null);
    setTables([]);
    console.log("Fetching table list via POST /api/list_tables...");
    try {
      const response = await fetch(`/api/list_tables`, { 
          method: 'POST',
          headers: {
              'Content-Type': 'application/json',
          },
          body: JSON.stringify({ connection_string: connectionString }),
          cache: 'no-store' 
      });
      const data = await response.json();

      if (!response.ok || !data.success) {
        setError(data.message || `Failed to fetch tables (status: ${response.status})`);
        setTables([]);
      } else {
        setTables(data.tables.map((name: string) => ({ name })));
      }
    } catch (err) {
      console.error("Fetch tables error:", err);
      setError(err instanceof Error ? err.message : "An unknown error occurred while fetching tables.");
      setTables([]);
    } finally {
      setIsLoading(false);
    }
  }, [isConnected, connectionString]); // Add dependencies for useCallback
  
  // Fetch tables when connection status changes to connected
  useEffect(() => {
    if (isConnected) {
        fetchTables();
    }
     else {
         setTables([]); // Clear tables if disconnected
         setError(null); // Clear errors if disconnected
     }
  }, [isConnected, fetchTables]); // Add fetchTables to dependency array

  // Renamed from handleListTables to avoid confusion
  const handleRefreshTables = () => {
    fetchTables(); 
  };

  const confirmDeleteTable = async () => {
    if (!tableToDelete) return;
    
    if (!isConnected || !connectionString) {
       setError("Database connection not established or invalid. Cannot delete table.");
       setTableToDelete(null); // Close dialog
       return;
    }

    setIsDeleting(tableToDelete);
    setError(null);
    const deletingName = tableToDelete;
    setTableToDelete(null); // Close dialog
    console.log(`Deleting table via /api/drop_table: ${deletingName}`);
    
    try {
      const response = await fetch('/api/drop_table', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        // Include connection string in the body
        body: JSON.stringify({ 
            table_name: deletingName, 
            connection_string: connectionString 
        }), 
      });
      
      const data = await response.json();

      if (!response.ok || !data.success) {
        setError(data.message || `Failed to delete table "${deletingName}" (status: ${response.status})`);
      } else {
        // Refresh table list after successful deletion
        await fetchTables(); 
      }
    } catch (err) {
       console.error("Delete table error:", err);
       setError(err instanceof Error ? err.message : `An unknown error occurred while deleting table ${deletingName}.`);
    }
    finally {
      setIsDeleting(null);
    }
  };

  const handleUseTable = (tableName: string) => {
      setSelectedTable(tableName);
      // Optionally provide feedback (e.g., highlight the row or show a temporary message)
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Table Management</CardTitle>
        <CardDescription>View and manage your TiDB vector tables.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && (
          <Alert variant="destructive">
            <XCircle className="h-4 w-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        <div className="table-container border rounded-md max-h-60 overflow-y-auto">
          <Table>
            <TableCaption>
              {tables.length === 0 && !isLoading 
                ? "No tables found or list not loaded yet." 
                : "List of existing vector tables."
              }
            </TableCaption>
            <TableHeader>
              <TableRow>
                <TableHead>Table Name</TableHead>
                <TableHead className="text-right pr-14">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {tables.map((table) => (
                <TableRow 
                    key={table.name}
                    className={selectedTableName === table.name ? 'bg-blue-50 dark:bg-blue-900/30' : ''}
                >
                  <TableCell className="font-medium">{table.name}</TableCell>
                  <TableCell className="text-right space-x-1">
                     <Button 
                       variant="outline" 
                       size="sm"
                       onClick={() => handleUseTable(table.name)}
                       disabled={selectedTableName === table.name}
                       title={`Use table ${table.name}`}
                     >
                        <CornerUpRight className="h-4 w-4 mr-1" /> Use
                     </Button>
                     <Dialog open={tableToDelete === table.name} onOpenChange={(open) => !open && setTableToDelete(null)}>
                       <DialogTrigger asChild>
                         <Button 
                           variant="ghost" 
                           size="icon" 
                           onClick={() => setTableToDelete(table.name)}
                           disabled={!!isDeleting} 
                           title={`Delete table ${table.name}`}
                           className="hover:bg-red-100 dark:hover:bg-red-900/50"
                         >
                           {isDeleting === table.name ? (
                             <Loader2 className="h-4 w-4 animate-spin" />
                           ) : (
                             <Trash2 className="h-4 w-4 text-red-500 hover:text-red-700" />
                           )}
                         </Button>
                       </DialogTrigger>
                       <DialogContent>
                         <DialogHeader>
                           <DialogTitle>Confirm Deletion</DialogTitle>
                           <DialogDescription>
                             Are you sure you want to delete the table &quot;{table.name}&quot;? 
                             This action also deletes the associated metadata table ({table.name}_metadata) if it exists. 
                             This action cannot be undone.
                           </DialogDescription>
                         </DialogHeader>
                         <DialogFooter>
                            <DialogClose asChild>
                              <Button variant="outline">Cancel</Button>
                            </DialogClose>
                           <Button 
                             variant="destructive" 
                             onClick={confirmDeleteTable} 
                             disabled={isDeleting === table.name}
                           >
                             {isDeleting === table.name && <Loader2 className="mr-2 h-4 w-4 animate-spin" />} 
                             Delete Table
                           </Button>
                         </DialogFooter>
                       </DialogContent>
                     </Dialog>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
      <CardFooter className="flex justify-start space-x-2">
        <Button variant="secondary" onClick={handleRefreshTables} disabled={!isConnected || isLoading || !!isDeleting}>
          {isLoading ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          {isLoading ? 'Loading...' : 'Refresh List'}
        </Button>
      </CardFooter>
    </Card>
  );
} 