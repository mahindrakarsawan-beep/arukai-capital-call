import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Arukai Capital Call",
  description: "Capital call management — v0.1",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;600&family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&display=swap"
          rel="stylesheet"
        />
      </head>
      <body className="min-h-screen bg-bg-bone text-fg-obsidian font-interface antialiased">
        {children}
      </body>
    </html>
  );
}
