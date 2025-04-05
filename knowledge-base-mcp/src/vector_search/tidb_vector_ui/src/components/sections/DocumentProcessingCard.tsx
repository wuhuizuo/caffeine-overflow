"use client";

import React, { useState, useRef, useEffect } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Loader2, Upload, FolderOpen, CheckCircle, XCircle, FileText, Trash2 } from 'lucide-react';
import { useConnection } from "@/context/ConnectionContext";
import { cn } from "@/lib/utils";

type DocSource = 'uploadFiles' | 'uploadDirectory';

interface ProcessResult {
  success: boolean;
  message: string;
}

export function DocumentProcessingCard() {
  const [tableName, setTableName] = useState('');
  const [docSource, setDocSource] = useState<DocSource>('uploadFiles');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ProcessResult | null>(null);
  const [foundDirFilesCount, setFoundDirFilesCount] = useState<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dirInputRef = useRef<HTMLInputElement>(null);
  const { connectionString, isConnected, selectedTableName, apiType, apiKey } = useConnection();

  useEffect(() => {
    if (selectedTableName) {
      setTableName(selectedTableName);
    }
  }, [selectedTableName]);

  // Add useEffect to set non-standard attribute after mount
  useEffect(() => {
    if (dirInputRef.current) {
      // Set the webkitdirectory attribute directly on the DOM node
      dirInputRef.current.setAttribute('webkitdirectory', '');
      // Optionally set directory as well, although webkitdirectory is the key one
      dirInputRef.current.setAttribute('directory', ''); 
    }
  }, []); // Empty dependency array ensures this runs only once on mount

  const handleFileSelectChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setFoundDirFilesCount(null);
    if (event.target.files) {
      const currentFileNames = new Set(selectedFiles.map(f => f.name + f.webkitRelativePath));
      const newFiles = Array.from(event.target.files).filter(
          file => !currentFileNames.has(file.name + file.webkitRelativePath) && file.name.endsWith('.md') 
      );
      const rejectedFiles = Array.from(event.target.files).filter(
          file => !file.name.endsWith('.md')
      );
      if (rejectedFiles.length > 0) {
          alert(`Warning: Only .md files are supported. ${rejectedFiles.length} other file(s) were ignored.`);
      }
      setSelectedFiles(prevFiles => [...prevFiles, ...newFiles]);
       if (fileInputRef.current) {
         fileInputRef.current.value = "";
       }
    }
  };
  
  const handleDirSelectChange = (event: React.ChangeEvent<HTMLInputElement>) => {
      setSelectedFiles([]);
      setFoundDirFilesCount(null);
      if (event.target.files) {
          const allFiles = Array.from(event.target.files);
          const mdFiles = allFiles.filter(file => file.name.endsWith('.md'));
          setFoundDirFilesCount(mdFiles.length);
          setSelectedFiles(mdFiles);
          console.log(`Found ${mdFiles.length} Markdown files in selected directory.`);
          if (allFiles.length > mdFiles.length) {
              alert(`Found ${mdFiles.length} Markdown (.md) files. ${allFiles.length - mdFiles.length} non-Markdown files were ignored.`);
          }
           if (dirInputRef.current) {
             dirInputRef.current.value = "";
           }
      }
  };

  const removeFile = (filePath: string) => {
    setSelectedFiles(prevFiles => prevFiles.filter(file => (file.webkitRelativePath || file.name) !== filePath));
  };

  const handleProcessDocuments = async () => {
    // Check connection string
    if (!isConnected || !connectionString) {
        setResult({ success: false, message: "Database connection not established or invalid." });
        console.error("handleProcessDocuments called without valid connection string");
        return;
    }
    // Add explicit check for API Type and Key from context
    if (!apiType || !apiKey) {
        setResult({ success: false, message: "API configuration is missing or invalid." });
        console.error("handleProcessDocuments called without valid API config");
        return;
    }
    // Check remaining form validity (table name, files selected)
    if (!isFormValid()) {
        // isFormValid logs details
        return;
    }
    
    setIsLoading(true);
    setResult(null);
    
    const formData = new FormData();
    // TypeScript now knows connectionString, apiType, and apiKey are not null here
    formData.append('connection_string', connectionString);
    formData.append('table_name', tableName);
    formData.append('api_key_type', apiType);
    formData.append('api_key', apiKey);
    selectedFiles.forEach(file => {
        formData.append('files[]', file, file.name);
    });
    
    console.log(`Sending ${selectedFiles.length} files to /api/upload_documents`);
    
    try {
      // Construct API URL using environment variable
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || '';
      const apiUrl = `${apiBaseUrl}/api/upload_documents`;
      console.log("Fetching from:", apiUrl);
      
      const response = await fetch(apiUrl, {
        method: 'POST',
        body: formData,
      });

      const data: ProcessResult = await response.json();

      if (!response.ok) {
        setResult({ 
          success: false, 
          message: data?.message || `Request failed with status: ${response.status}` 
        });
      } else {
        setResult({ 
          success: data.success, 
          message: data.message 
        });
      }
    } catch (error) {
      console.error("Failed to process documents:", error);
      setResult({ 
        success: false, 
        message: error instanceof Error ? error.message : "An unknown error occurred while contacting the server."
      });
    } finally {
        setIsLoading(false);
    }
  };
  
  // isFormValid check - uses top-level context vars for logging only
  const isFormValid = (): boolean => {
    // Remove the hook call from here
    // const { apiType: currentApiType, apiKey: currentApiKey } = useConnection(); 
    
    // Validation logic simplified: checks only remaining fields
    const valid = !!tableName && selectedFiles.length > 0; 
    
    if (!valid) {
        // Logging still uses top-level context vars for debugging context
        console.log('isFormValid check failed (Processing - Step 2: Table/Files):', {
            isConnected, // Log top-level context value
            tableName: !!tableName,
            apiType: !!apiType, // Log top-level context value
            apiKey: !!apiKey,   // Log top-level context value
            selectedFilesCount: selectedFiles.length
        });
    }
    return valid;
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Document Processing</CardTitle>
        <CardDescription>Upload documents or specify a directory to process and store vectors in TiDB.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        {/* Row 1: Table Name */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2 md:col-span-3">
            <Label htmlFor="table-name">Select Vector Table</Label>
            <Input id="table-name" placeholder="TiDB vector table used for providing vector storage." value={tableName} onChange={(e) => setTableName(e.target.value)} disabled={isLoading} />
          </div>
        </div>

        {/* Row 2: Document Source */}
        <Tabs 
            value={docSource} 
            onValueChange={(value) => {
                setDocSource(value as DocSource);
                setSelectedFiles([]);
                setFoundDirFilesCount(null);
            }} 
            className="w-full"
        >
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="uploadFiles" disabled={isLoading}><Upload className="mr-2 h-4 w-4"/>Upload Files</TabsTrigger>
            <TabsTrigger value="uploadDirectory" disabled={isLoading}><FolderOpen className="mr-2 h-4 w-4"/>Upload Directory</TabsTrigger>
          </TabsList>
          <TabsContent value="uploadFiles" className="mt-4 space-y-4">
            <div className="space-y-2">
                <Label>Select Files (Markdown .md only)</Label>
                <Input 
                    id="file-upload" 
                    type="file" 
                    multiple 
                    ref={fileInputRef}
                    onChange={handleFileSelectChange}
                    disabled={isLoading} 
                    className="sr-only" 
                    accept=".md"
                />
                <Label 
                    htmlFor="file-upload" 
                    className={cn(
                        "inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                        "border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 px-4 py-2",
                        isLoading ? "cursor-not-allowed opacity-50" : "cursor-pointer"
                    )}
                >
                    <Upload className="mr-2 h-4 w-4"/>
                    Choose Files...
                </Label>
                {selectedFiles.length > 0 && docSource === 'uploadFiles' && (
                    <span className="ml-3 text-sm text-muted-foreground">
                        {selectedFiles.length} file(s) selected for upload
                    </span>
                )}
            </div>
            {selectedFiles.length > 0 && docSource === 'uploadFiles' && (
                <div className="space-y-2 border rounded-md p-3 max-h-40 overflow-y-auto">
                    <Label>Files Queued for Upload:</Label>
                    {selectedFiles.map(file => {
                        const filePath = file.webkitRelativePath || file.name;
                        return (
                            <div key={filePath} className="flex items-center justify-between text-sm bg-gray-50 dark:bg-gray-800 p-1.5 rounded">
                                <div className="flex items-center overflow-hidden whitespace-nowrap text-ellipsis">
                                    <FileText className="h-4 w-4 mr-2 flex-shrink-0" />
                                    <span className="overflow-hidden text-ellipsis" title={filePath}>{filePath}</span>
                                </div>
                                <Button variant="ghost" size="icon" onClick={() => removeFile(filePath)} disabled={isLoading} className="h-6 w-6 ml-2">
                                    <Trash2 className="h-4 w-4 text-muted-foreground"/>
                                </Button>
                            </div>
                        )
                    })}
                </div>
            )}
          </TabsContent>
          <TabsContent value="uploadDirectory" className="mt-4 space-y-4">
            <div className="space-y-2">
                <Label>Select Local Directory (contains .md files)</Label>
                 <input
                    id="dir-upload"
                    type="file"
                    ref={dirInputRef}
                    onChange={handleDirSelectChange}
                    disabled={isLoading}
                    className="sr-only"
                    accept=".md"
                    multiple
                />
                <Label
                    htmlFor="dir-upload"
                    className={cn(
                        "inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                        "border border-input bg-background hover:bg-accent hover:text-accent-foreground h-10 px-4 py-2",
                        isLoading ? "cursor-not-allowed opacity-50" : "cursor-pointer"
                    )}
                >
                    <FolderOpen className="mr-2 h-4 w-4" />
                    Choose Directory...
                </Label>
                 {foundDirFilesCount !== null && (
                     <p className="text-sm text-muted-foreground">
                         Found {foundDirFilesCount} Markdown (.md) file(s) in the selected directory.
                         {foundDirFilesCount > 0 ? ' These will be uploaded.' : ''}
                     </p>
                )}
                 {selectedFiles.length > 0 && docSource === 'uploadDirectory' && (
                    <div className="space-y-2 border rounded-md p-3 max-h-40 overflow-y-auto">
                        <Label>Files Found (.md only) & Queued for Upload:</Label>
                        {selectedFiles.map(file => {
                            const filePath = file.webkitRelativePath || file.name;
                            return (
                                <div key={filePath} className="flex items-center justify-between text-sm bg-gray-50 dark:bg-gray-800 p-1.5 rounded">
                                    <div className="flex items-center overflow-hidden whitespace-nowrap text-ellipsis">
                                        <FileText className="h-4 w-4 mr-2 flex-shrink-0" />
                                        <span className="overflow-hidden text-ellipsis" title={filePath}>{filePath}</span>
                                    </div>
                                     <Button variant="ghost" size="icon" onClick={() => removeFile(filePath)} disabled={isLoading} className="h-6 w-6 ml-2">
                                        <Trash2 className="h-4 w-4 text-muted-foreground"/>
                                    </Button>
                                </div>
                            )
                        })}
                    </div>
                 )}
            </div>
          </TabsContent>
        </Tabs>
        
        {/* Progress/Result Area */}
        {isLoading && (
             <div className="flex items-center text-sm text-muted-foreground">
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Processing documents... This may take a while depending on the size and number of documents.
             </div>
        )}
        {result && !isLoading && (
            <Alert variant={result.success ? 'default' : 'destructive'}>
              {result.success ? <CheckCircle className="h-4 w-4" /> : <XCircle className="h-4 w-4" />}
              <AlertTitle>{result.success ? 'Processing Complete' : 'Processing Failed'}</AlertTitle>
              <AlertDescription>{result.message}</AlertDescription>
            </Alert>
        )}

      </CardContent>
      <CardFooter>
        <Button 
            onClick={handleProcessDocuments} 
            disabled={!isConnected || isLoading || !isFormValid()} 
        >
          {isLoading ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
          Process {selectedFiles.length > 0 ? `${selectedFiles.length} ` : ''}Document(s)
        </Button>
      </CardFooter>
    </Card>
  );
} 