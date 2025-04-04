import {
  Alert, AlertDescription, AlertTitle 
} from "@/components/ui/alert";
import { Terminal } from "lucide-react";
import { DatabaseConnectionCard } from "@/components/sections/DatabaseConnectionCard";
import { TableManagementCard } from "@/components/sections/TableManagementCard";
import { ApiConfigurationCard } from "@/components/sections/ApiConfigurationCard";
import { DocumentProcessingCard } from "@/components/sections/DocumentProcessingCard";
import { RetrievalTestingCard } from "@/components/sections/RetrievalTestingCard";

export default function Home() {
  return (
    <div className="min-h-screen">
      {/* Header - Use a primary-related or card-like background */}
      {/* Using a darker cool gray/charcoal similar to primary text */}
      <header className="bg-[oklch(0.20_0.02_250)] dark:bg-[oklch(0.22_0.015_250)] text-primary-foreground py-4 mb-8 shadow-sm">
        <div className="container mx-auto px-4">
          <h1 className="text-2xl font-semibold">
            TiDB Vector Document Processing System
          </h1>
          <p className="text-sm opacity-90">
            An elegant interface for document vectorization & storage in TiDB Serverless.<br />
            <span className="opacity-75">Happy PingCAP 10th Anniversary!</span>
          </p>
        </div>
      </header>

      {/* Main Content - Restructure grid */}
      <main className="container mx-auto px-4 pb-8">
        {/* Security Notice (Spans full width above columns) */}
        <div className="mb-6">
          <Alert variant="default">
            <Terminal className="h-4 w-4" />
            <AlertTitle>Security Notice</AlertTitle>
            <AlertDescription>
              Sensitive information like TiDB connection strings and API keys are
              only used in the current session and will not be permanently stored.
              Please clear your browser cache after using this application in a
              shared environment.
            </AlertDescription>
          </Alert>
        </div>

        {/* Two-Column Layout for Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Left Column: Configuration & Management */}
          <div className="space-y-6">
            <DatabaseConnectionCard />
            <ApiConfigurationCard />
            <TableManagementCard />
          </div>

          {/* Right Column: Processing & Testing */}
          <div className="space-y-6">
            <DocumentProcessingCard />
            <RetrievalTestingCard />
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="container mx-auto px-4 mt-8 py-4 text-center text-muted-foreground text-sm border-t border-border">
        Built by Team Caffeine-Overflow
      </footer>
    </div>
  );
}
