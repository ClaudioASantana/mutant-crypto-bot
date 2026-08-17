import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  allowedDevOrigins: ['192.168.1.9', 'localhost', '127.0.0.1'],
  /* config options here */
  async rewrites() {
    // Proxy HTTP para o backend (apenas DEV local, mesmos hosts).
    // Em Docker/staging o frontend usa NEXT_PUBLIC_API_PORT com URL direta.
    // Observacao: rewrites NAO cobrem WebSocket (/ws) — o frontend connecta
    // via ws:// direto no backend, entao nada quebra.
    return [
      {
        source: '/api/:path*',
        destination: 'http://localhost:8000/api/:path*',
      },
    ];
  },
};

export default nextConfig;
