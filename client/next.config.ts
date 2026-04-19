import type { NextConfig } from 'next';
import path from 'path';

/**
 * When NEXT_PUBLIC_API_URL is a same-origin path (e.g. /api), the browser calls the Next.js dev
 * server. Rewrite those requests to the real FastAPI process (Docker backend on the host).
 * Production builds skip this (NODE_ENV !== development).
 */
function devApiRewrites():
  | Promise<{ source: string; destination: string }[]>
  | { source: string; destination: string }[] {
  if (process.env.NODE_ENV !== 'development') {
    return [];
  }
  const publicApi = (process.env.NEXT_PUBLIC_API_URL || '/api').trim();
  if (
    publicApi.startsWith('http://') ||
    publicApi.startsWith('https://')
  ) {
    return [];
  }
  const subpath = publicApi.replace(/\/$/, '') || '/api';
  const proxyOrigin = (
    process.env.NEXT_DEV_PROXY_API_ORIGIN || 'http://127.0.0.1:8000'
  ).replace(/\/$/, '');
  return [
    {
      source: `${subpath}/:path*`,
      destination: `${proxyOrigin}${subpath}/:path*`,
    },
  ];
}

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  eslint: {
    ignoreDuringBuilds: true,
  },
  webpack: (config) => {
    config.resolve.alias = {
      ...(config.resolve.alias || {}),
      '@': path.resolve(__dirname, 'src'),
    };
    return config;
  },
  async rewrites() {
    return devApiRewrites();
  },
};

export default nextConfig;
