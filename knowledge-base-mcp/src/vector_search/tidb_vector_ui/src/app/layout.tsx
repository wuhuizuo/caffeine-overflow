import type { Metadata } from "next";
import "./globals.css";
import { ConnectionProvider } from "@/context/ConnectionContext";

export const metadata: Metadata = {
  title: "TiDB Vector UI",
  description: "Modern UI for TiDB Vector Document Processing System",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`font-sans antialiased`}>
        <ConnectionProvider>
          {children}
        </ConnectionProvider>
      </body>
    </html>
  );
}
