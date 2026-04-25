import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import Script from "next/script";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Mai Filer — Nigerian Tax e-Filing",
  description: "AI-native Nigerian tax e-filing platform. File your PIT/PAYE return for 2026.",
};

// Restore path encoded by public/404.html (GitHub Pages SPA trick)
const spaRedirectScript = `
(function(l) {
  if (l.search[1] === '/') {
    var decoded = l.search.slice(1).split('&').map(function(s) {
      return s.replace(/~and~/g, '&');
    });
    window.history.replaceState(null, null,
      l.pathname.slice(0, -1) + decoded[0] +
      (decoded[1] ? '?' + decoded[1] : '') + l.hash
    );
  }
}(window.location));
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <head>
        <Script id="spa-redirect" strategy="beforeInteractive">
          {spaRedirectScript}
        </Script>
      </head>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
