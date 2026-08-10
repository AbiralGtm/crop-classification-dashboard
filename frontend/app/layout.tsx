import type { Metadata } from "next";
import "./globals.css";
import "leaflet/dist/leaflet.css";
import "leaflet-draw/dist/leaflet.draw.css";

export const metadata: Metadata = {
  title: "Crop Classification Dashboard",
  description: "Satellite imagery crop classification for Rupandehi District and beyond",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="h-screen w-screen overflow-hidden bg-gray-50 text-gray-900">
        {children}
      </body>
    </html>
  );
}
