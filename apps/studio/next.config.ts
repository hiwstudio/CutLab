import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ['127.0.0.1'],
  async rewrites() {
    return [
      { source: "/api/:path*", destination: "http://127.0.0.1:8787/api/:path*" },
      { source: "/media/:path*", destination: "http://127.0.0.1:8787/media/:path*" },
      { source: "/ws", destination: "http://127.0.0.1:8787/ws" },
    ];
  },
};

export default nextConfig;
