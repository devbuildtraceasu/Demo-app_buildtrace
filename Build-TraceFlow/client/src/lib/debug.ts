/**
 * Debug utilities for frontend troubleshooting
 * These are only active in development mode
 */

export function logApiConfig() {
  if (import.meta.env.DEV) {
    const apiUrl = import.meta.env.VITE_API_URL;
    console.group('🔧 API Configuration');
    console.log('VITE_API_URL:', apiUrl || '(not set)');
    console.log('Environment:', import.meta.env.MODE);
    console.log('Base URL:', window.location.origin);
    console.groupEnd();
  }
}

export function logButtonClick(buttonName: string, details?: Record<string, unknown>) {
  if (import.meta.env.DEV) {
    console.log(`[Button Click] ${buttonName}`, details || '');
  }
}

export function logApiCall(method: string, url: string, status?: number) {
  if (import.meta.env.DEV) {
    const emoji = status && status >= 200 && status < 300 ? '✅' : status && status >= 400 ? '❌' : '🔄';
    console.log(`${emoji} [API] ${method} ${url}`, status ? `(${status})` : '');
  }
}

// Auto-log API config on module load in development
if (import.meta.env.DEV) {
  logApiConfig();
}
