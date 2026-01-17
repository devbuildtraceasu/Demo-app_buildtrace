/**
 * React Query hooks for drawings data
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, { Drawing, Sheet, Block } from '@/lib/api';

// Fetch drawings for a project
export function useDrawings(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project', projectId, 'drawings'],
    queryFn: () => api.drawings.listByProject(projectId!),
    enabled: !!projectId,
  });
}

// Fetch a single drawing
export function useDrawing(drawingId: string | undefined) {
  return useQuery({
    queryKey: ['drawing', drawingId],
    queryFn: () => api.drawings.get(drawingId!),
    enabled: !!drawingId,
  });
}

// Fetch sheets for a drawing
export function useSheets(drawingId: string | undefined) {
  return useQuery({
    queryKey: ['drawing', drawingId, 'sheets'],
    queryFn: () => api.drawings.getSheets(drawingId!),
    enabled: !!drawingId,
  });
}

// Fetch sheets for a drawing, sorted by sheet_number descending
export function useSheetsDescending(drawingId: string | undefined) {
  return useQuery({
    queryKey: ['drawing', drawingId, 'sheets', 'descending'],
    queryFn: async () => {
      const sheets = await api.drawings.getSheets(drawingId!);
      return sheets.sort((a, b) =>
        (b.sheet_number || '').localeCompare(a.sheet_number || '', undefined, { numeric: true })
      );
    },
    enabled: !!drawingId,
  });
}

// Fetch drawings for a project, sorted by created_at descending
export function useDrawingsDescending(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project', projectId, 'drawings', 'descending'],
    queryFn: async () => {
      const drawings = await api.drawings.listByProject(projectId!);
      return drawings.sort((a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
      );
    },
    enabled: !!projectId,
  });
}

// Create a new drawing
export function useCreateDrawing() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: { project_id: string; filename: string; name?: string; uri: string }) =>
      api.drawings.create(data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['project', variables.project_id, 'drawings'] });
    },
  });
}

// Fetch all blocks (optionally filtered by type)
export function useBlocks(blockType?: string) {
  return useQuery({
    queryKey: ['blocks', blockType],
    queryFn: () => api.blocks.listAll(blockType),
  });
}

// Fetch blocks for a specific sheet
export function useBlocksBySheet(sheetId: string | undefined) {
  return useQuery({
    queryKey: ['sheet', sheetId, 'blocks'],
    queryFn: () => api.blocks.listBySheet(sheetId!),
    enabled: !!sheetId,
  });
}

// Fetch blocks for a specific drawing
export function useBlocksByDrawing(drawingId: string | undefined) {
  return useQuery({
    queryKey: ['drawing', drawingId, 'blocks'],
    queryFn: () => api.drawings.getBlocks(drawingId!),
    enabled: !!drawingId,
  });
}

// Fetch drawing status with polling (for tracking preprocessing progress)
export function useDrawingStatus(drawingId: string | undefined) {
  return useQuery({
    queryKey: ['drawing', drawingId, 'status'],
    queryFn: () => {
      console.log(`[useDrawingStatus] Fetching status for drawing: ${drawingId}`);
      return api.drawings.getStatus(drawingId!);
    },
    enabled: !!drawingId,
    // Poll every 2 seconds while processing
    refetchInterval: (query) => {
      const data = query.state.data;
      if (data?.status === 'processing' || data?.status === 'pending') {
        return 2000; // Poll every 2 seconds
      }
      // Continue polling briefly after completion to ensure blocks are loaded
      if (data?.status === 'completed' && (!data?.blocks || data.blocks.length === 0)) {
        return 2000; // Keep polling if completed but no blocks yet
      }
      return false; // Stop polling when complete with blocks or failed
    },
    staleTime: 0, // Always consider data stale to ensure fresh fetches
    refetchOnMount: true, // Always refetch when component mounts
    refetchOnWindowFocus: true, // Refetch when window regains focus
  });
}

