/**
 * Simplified environment variables for development
 */

// No-op export for compatibility
export const env = {
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000',
  NEXT_PUBLIC_APP_URL: process.env.NEXT_PUBLIC_APP_URL || 'http://localhost:3000',
  NODE_ENV: process.env.NODE_ENV || 'development',
  NEXT_PUBLIC_ENABLE_ROMANTIC_MODE: process.env.NEXT_PUBLIC_ENABLE_ROMANTIC_MODE || 'false',
  NEXT_PUBLIC_ENABLE_CREATIVE_MODE: process.env.NEXT_PUBLIC_ENABLE_CREATIVE_MODE || 'true',
  NEXT_PUBLIC_ENABLE_PRO_FEATURES: process.env.NEXT_PUBLIC_ENABLE_PRO_FEATURES || 'false',
};

export function isFeatureEnabled(feature: string): boolean {
  if (feature.toUpperCase() === 'ROMANTIC') {
    return env.NEXT_PUBLIC_ENABLE_ROMANTIC_MODE === 'true';
  }
  if (feature.toUpperCase() === 'CREATIVE') {
    return env.NEXT_PUBLIC_ENABLE_CREATIVE_MODE === 'true';
  }
  if (feature.toUpperCase() === 'PRO_FEATURES') {
    return env.NEXT_PUBLIC_ENABLE_PRO_FEATURES === 'true';
  }
  return false;
}

export function getApiUrl(): string {
  return env.NEXT_PUBLIC_API_URL;
}

export function getWsUrl(): string {
  return env.NEXT_PUBLIC_WS_URL;
}

export function isProduction(): boolean {
  return env.NODE_ENV === 'production';
}

export function isDevelopment(): boolean {
  return env.NODE_ENV === 'development';
}
