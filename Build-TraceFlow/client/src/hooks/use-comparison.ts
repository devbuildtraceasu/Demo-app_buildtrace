/**
 * React Query hooks for comparison data
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, { Comparison, Change } from '@/lib/api';

// Fetch a single comparison
export function useComparison(comparisonId: string | undefined) {
  return useQuery({
    queryKey: ['comparison', comparisonId],
    queryFn: () => api.comparisons.get(comparisonId!),
    enabled: !!comparisonId,
    // TanStack Query v5: refetchInterval receives query object, not data directly
    refetchInterval: (query) => {
      const data = query.state.data as Comparison | undefined;
      // Poll while processing
      if (data?.status === 'processing') {
        return 2000; // Poll every 2 seconds for faster updates
      }
      // Stop polling when complete or failed
      return false;
    },
  });
}

// Fetch changes for a comparison
export function useChanges(comparisonId: string | undefined) {
  return useQuery({
    queryKey: ['comparison', comparisonId, 'changes'],
    queryFn: () => api.comparisons.getChanges(comparisonId!),
    enabled: !!comparisonId,
  });
}

// Create a new change
export function useCreateChange(comparisonId: string) {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: Partial<Change>) => api.comparisons.createChange(comparisonId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comparison', comparisonId, 'changes'] });
    },
  });
}

// Update a change
export function useUpdateChange() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ changeId, data }: { changeId: string; data: Partial<Change> }) =>
      api.comparisons.updateChange(changeId, data),
    onSuccess: (_, { changeId }) => {
      // Find and invalidate the related comparison query
      queryClient.invalidateQueries({ queryKey: ['comparison'] });
    },
  });
}

// Delete a change
export function useDeleteChange() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (changeId: string) => api.comparisons.deleteChange(changeId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['comparison'] });
    },
  });
}

// List comparisons for a project
export function useComparisons(projectId: string | undefined) {
  return useQuery({
    queryKey: ['project', projectId, 'comparisons'],
    queryFn: () => api.comparisons.listByProject(projectId!),
    enabled: !!projectId,
  });
}

// Create a new comparison
export function useCreateComparison() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: {
      project_id: string;
      drawing_a_id: string;
      drawing_b_id: string;
      sheet_a_id?: string;
      sheet_b_id?: string;
    }) => api.comparisons.create(data),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['project', variables.project_id, 'comparisons'] });
    },
  });
}

