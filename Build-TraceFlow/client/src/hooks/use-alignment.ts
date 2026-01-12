/**
 * React Query hooks for manual alignment
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';

const API_BASE = import.meta.env.VITE_API_URL || '/api';

export interface Point {
  x: number;
  y: number;
}

export interface ManualAlignmentRequest {
  overlay_id: string;
  source_points: Point[];
  target_points: Point[];
}

export interface ManualAlignmentResponse {
  overlay_id: string;
  job_id: string;
  status: string;
  message: string;
  scale?: number;
  rotation_deg?: number;
  translate_x?: number;
  translate_y?: number;
}

export interface AlignmentPreviewResponse {
  valid: boolean;
  scale: number;
  rotation_deg: number;
  translate_x: number;
  translate_y: number;
  matrix: number[][];
  warnings: string[];
}

async function submitManualAlignment(data: ManualAlignmentRequest): Promise<ManualAlignmentResponse> {
  const token = localStorage.getItem('auth_token');
  const response = await fetch(`${API_BASE}/alignment/manual`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to submit manual alignment');
  }

  return response.json();
}

async function previewAlignment(data: ManualAlignmentRequest): Promise<AlignmentPreviewResponse> {
  const token = localStorage.getItem('auth_token');
  const response = await fetch(`${API_BASE}/alignment/preview`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(data),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to preview alignment');
  }

  return response.json();
}

export function useManualAlignment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: submitManualAlignment,
    onSuccess: (data) => {
      // Invalidate the comparison to refetch with new overlay
      queryClient.invalidateQueries({ queryKey: ['comparison', data.overlay_id] });
    },
  });
}

export function useAlignmentPreview() {
  return useMutation({
    mutationFn: previewAlignment,
  });
}

/**
 * Helper to manage point collection state
 */
export interface AlignmentPointsState {
  sourcePoints: Point[];
  targetPoints: Point[];
  currentMode: 'source' | 'target';
  isComplete: boolean;
}

export function createInitialAlignmentState(): AlignmentPointsState {
  return {
    sourcePoints: [],
    targetPoints: [],
    currentMode: 'source',
    isComplete: false,
  };
}

export function addAlignmentPoint(
  state: AlignmentPointsState,
  point: Point,
): AlignmentPointsState {
  if (state.currentMode === 'source' && state.sourcePoints.length < 3) {
    const newSourcePoints = [...state.sourcePoints, point];
    const switchToTarget = newSourcePoints.length === 3;
    return {
      ...state,
      sourcePoints: newSourcePoints,
      currentMode: switchToTarget ? 'target' : 'source',
    };
  }

  if (state.currentMode === 'target' && state.targetPoints.length < 3) {
    const newTargetPoints = [...state.targetPoints, point];
    const isComplete = newTargetPoints.length === 3;
    return {
      ...state,
      targetPoints: newTargetPoints,
      isComplete,
    };
  }

  return state;
}

export function resetAlignmentPoints(): AlignmentPointsState {
  return createInitialAlignmentState();
}

