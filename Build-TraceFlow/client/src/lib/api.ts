/**
 * BuildTrace API Client
 * Provides typed functions for all API endpoints
 */

// Ensure API_BASE includes /api prefix
const BASE_URL = import.meta.env.VITE_API_URL || '';
const API_BASE = BASE_URL.endsWith('/api') ? BASE_URL : BASE_URL ? `${BASE_URL}/api` : '/api';

// Log API configuration in development
if (import.meta.env.DEV) {
  console.log('[API Config] VITE_API_URL:', import.meta.env.VITE_API_URL);
  console.log('[API Config] API_BASE:', API_BASE);
}

// Types
export interface User {
  id: string;
  email: string;
  first_name?: string;
  last_name?: string;
  profile_image_url?: string;
}

export interface Project {
  id: string;
  name: string;
  description?: string;
  organization_id: string;
  project_number?: string;
  address?: string;
  project_type?: string;
  phase?: string;
  created_at: string;
  updated_at: string;
}

export interface Drawing {
  id: string;
  project_id: string;
  filename: string;
  name?: string;
  uri: string;
  sheet_count: number;
  job_id?: string;
  status?: string;
  created_at: string;
  updated_at: string;
}

export interface DrawingStatus {
  drawing_id: string;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  job_id?: string;
  sheet_count: number;
  block_count: number;
  blocks: Array<{
    id: string;
    type?: string;
    description?: string;
    uri?: string;
  }>;
}

export interface Sheet {
  id: string;
  drawing_id: string;
  index: number;
  uri: string;
  title?: string;
  sheet_number?: string;
  discipline?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Block {
  id: string;
  sheet_id: string;
  type?: string;
  uri?: string;
  bounds?: { xmin: number; ymin: number; xmax: number; ymax: number };
  ocr?: string;
  description?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Comparison {
  id: string;
  project_id: string;
  drawing_a_id: string;
  drawing_b_id: string;
  sheet_a_id?: string;
  sheet_b_id?: string;
  status: string;
  overlay_uri?: string;
  addition_uri?: string;
  deletion_uri?: string;
  score?: number;
  change_count: number;
  total_cost_impact?: string;
  total_schedule_impact?: string;
  created_at: string;
  updated_at: string;
}

export interface Change {
  id: string;
  comparison_id: string;
  type: 'added' | 'removed' | 'modified';
  title: string;
  description?: string;
  bounds?: { xmin: number; ymin: number; xmax: number; ymax: number };
  trade?: string;
  discipline?: string;
  estimated_cost?: string;
  schedule_impact?: string;
  status: string;
  assignee?: string;
  created_at: string;
  updated_at: string;
}

export interface Job {
  id: string;
  type: string;
  status: 'queued' | 'started' | 'completed' | 'failed' | 'canceled';
  project_id?: string;
  target_type: string;
  target_id: string;
  created_at: string;
  updated_at: string;
}

// Auth token management
let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
  if (token) {
    localStorage.setItem('auth_token', token);
  } else {
    localStorage.removeItem('auth_token');
  }
}

export function getAuthToken(): string | null {
  if (authToken) return authToken;
  authToken = localStorage.getItem('auth_token');
  return authToken;
}

// HTTP helpers
async function fetchWithAuth(url: string, options: RequestInit = {}): Promise<Response> {
  const token = getAuthToken();
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (token) {
    (headers as Record<string, string>)['Authorization'] = `Bearer ${token}`;
  }

  const fullUrl = `${API_BASE}${url}`;
  
  // Log in development
  if (import.meta.env.DEV) {
    console.log('[API Request]', options.method || 'GET', fullUrl);
  }

  try {
    const response = await fetch(fullUrl, {
      ...options,
      headers,
    });

    if (response.status === 401) {
      setAuthToken(null);
      // Don't redirect immediately - let the component handle it
      // This prevents breaking the UI flow
      if (import.meta.env.DEV) {
        console.warn('[API] Unauthorized - token cleared');
      }
      throw new Error('Unauthorized');
    }

    if (!response.ok && import.meta.env.DEV) {
      console.error('[API Error]', response.status, response.statusText, fullUrl);
    }

    return response;
  } catch (error) {
    if (import.meta.env.DEV) {
      console.error('[API Request Failed]', error, fullUrl);
    }
    throw error;
  }
}

async function get<T>(url: string): Promise<T> {
  const response = await fetchWithAuth(url);
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json();
}

async function post<T>(url: string, data?: unknown): Promise<T> {
  const response = await fetchWithAuth(url, {
    method: 'POST',
    body: data ? JSON.stringify(data) : undefined,
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json();
}

async function patch<T>(url: string, data: unknown): Promise<T> {
  const response = await fetchWithAuth(url, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
  return response.json();
}

async function del(url: string): Promise<void> {
  const response = await fetchWithAuth(url, {
    method: 'DELETE',
  });
  if (!response.ok) {
    throw new Error(`API error: ${response.status}`);
  }
}

// Auth API
export const auth = {
  login: async (email: string, password: string) => {
    const response = await post<{ access_token: string; user: User }>('/auth/login', { email, password });
    setAuthToken(response.access_token);
    return response;
  },
  logout: async () => {
    await post('/auth/logout');
    setAuthToken(null);
  },
  me: () => get<User | null>('/auth/me'),
  getGoogleAuthUrl: () => get<{ url: string }>('/auth/google/url'),
};

// Projects API
export const projects = {
  list: () => get<Project[]>('/projects'),
  get: (id: string) => get<Project>(`/projects/${id}`),
  create: (data: { name: string; description?: string }) => post<Project>('/projects', data),
  update: (id: string, data: Partial<Project>) => patch<Project>(`/projects/${id}`, data),
  delete: (id: string) => del(`/projects/${id}`),
};

// Drawings API
export const drawings = {
  listByProject: (projectId: string) => get<Drawing[]>(`/drawings/project/${projectId}`),
  get: (id: string) => get<Drawing>(`/drawings/${id}`),
  getSheets: (drawingId: string) => get<Sheet[]>(`/drawings/${drawingId}/sheets`),
  getBlocks: (drawingId: string) => get<Block[]>(`/drawings/${drawingId}/blocks`),
  getStatus: (drawingId: string) => get<DrawingStatus>(`/drawings/${drawingId}/status`),
  create: (data: { project_id: string; filename: string; name?: string; uri: string }) => 
    post<Drawing>('/drawings', data),
};

// Blocks API
export const blocks = {
  listAll: (blockType?: string) => {
    const params = blockType ? `?block_type=${blockType}` : '';
    return get<Block[]>(`/drawings/blocks${params}`);
  },
  listBySheet: (sheetId: string) => get<Block[]>(`/drawings/sheets/${sheetId}/blocks`),
};

// Comparisons API
export const comparisons = {
  listByProject: (projectId: string) => get<Comparison[]>(`/comparisons/project/${projectId}`),
  get: (id: string) => get<Comparison>(`/comparisons/${id}`),
  create: (data: {
    project_id: string;
    drawing_a_id: string;
    drawing_b_id: string;
    sheet_a_id?: string;
    sheet_b_id?: string;
  }) => post<Comparison>('/comparisons', data),
  getChanges: (comparisonId: string) => get<Change[]>(`/comparisons/${comparisonId}/changes`),
  createChange: (comparisonId: string, data: Partial<Change>) =>
    post<Change>(`/comparisons/${comparisonId}/changes`, data),
  updateChange: (changeId: string, data: Partial<Change>) =>
    patch<Change>(`/comparisons/changes/${changeId}`, data),
  deleteChange: (changeId: string) => del(`/comparisons/changes/${changeId}`),
};

// Jobs API
export const jobs = {
  list: (params?: { project_id?: string; status?: string }) => {
    const searchParams = new URLSearchParams();
    if (params?.project_id) searchParams.set('project_id', params.project_id);
    if (params?.status) searchParams.set('status_filter', params.status);
    return get<Job[]>(`/jobs?${searchParams.toString()}`);
  },
  get: (id: string) => get<Job>(`/jobs/${id}`),
  cancel: (id: string) => post<Job>(`/jobs/${id}/cancel`),
};

// Analysis API - AI-powered change detection and cost analysis
export interface AnalysisResult {
  job_id: string;
  message: string;
}

export interface AnalysisSummary {
  overlay_id: string;
  changes: Change[];
  summary: {
    total_cost_impact?: string;
    total_schedule_impact?: string;
    biggest_cost_driver?: string;
    analysis_summary?: string;
    change_count: number;
  } | null;
}

export const analysis = {
  detectChanges: (overlayId: string, includeCostEstimate: boolean = true) =>
    post<AnalysisResult>('/analysis/detect-changes', { 
      overlay_id: overlayId, 
      include_cost_estimate: includeCostEstimate 
    }),
  analyzeCost: (overlayId: string) =>
    post<AnalysisResult>('/analysis/cost', { overlay_id: overlayId }),
  getSummary: (overlayId: string) =>
    get<AnalysisSummary>(`/analysis/summary/${overlayId}`),
  // Note: endpoint is /analysis/summary/{overlay_id}
};

// Uploads API
export const uploads = {
  getSignedUrl: (filename: string, contentType: string = 'application/pdf', projectId?: string) =>
    post<{ upload_url: string; remote_path: string; expires_in: number }>('/uploads/signed-url', {
      filename,
      content_type: contentType,
      project_id: projectId,
    }),
  getDownloadUrl: (remotePath: string) =>
    get<{ download_url: string; remote_path: string; expires_in: number }>(`/uploads/download-url/${remotePath}`),
  uploadDirect: async (file: File, projectId?: string) => {
    const formData = new FormData();
    formData.append('file', file);
    
    const token = getAuthToken();
    const headers: HeadersInit = {};
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    
    const url = projectId 
      ? `${API_BASE}/uploads/direct?project_id=${projectId}`
      : `${API_BASE}/uploads/direct`;
    
    const response = await fetch(url, {
      method: 'POST',
      headers,
      body: formData,
    });
    
    if (!response.ok) {
      throw new Error(`Upload failed: ${response.status}`);
    }
    
    return response.json() as Promise<{ uri: string; remote_path: string; filename: string; size: number }>;
  },
};

// WebSocket for job status updates
export function subscribeToJob(jobId: string, onMessage: (data: unknown) => void): WebSocket {
  const wsUrl = API_BASE.replace(/^http/, 'ws') + `/jobs/ws/${jobId}`;
  const ws = new WebSocket(wsUrl);
  
  ws.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      onMessage(data);
    } catch {
      console.error('Failed to parse WebSocket message');
    }
  };

  return ws;
}

export default {
  auth,
  projects,
  drawings,
  blocks,
  comparisons,
  jobs,
  uploads,
  analysis,
  subscribeToJob,
};

