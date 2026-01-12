/**
 * React hooks for file uploads
 */

import { useState, useCallback } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/lib/api';

export interface UploadProgress {
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'processing' | 'complete' | 'error';
  uri?: string;
  error?: string;
}

export function useFileUpload(projectId?: string) {
  const [uploads, setUploads] = useState<UploadProgress[]>([]);
  const queryClient = useQueryClient();

  const uploadFile = useCallback(async (file: File): Promise<string> => {
    // Update status to uploading
    setUploads(prev => [
      ...prev.filter(u => u.file.name !== file.name),
      { file, progress: 0, status: 'uploading' },
    ]);

    try {
      // Get signed URL
      const { upload_url, remote_path } = await api.uploads.getSignedUrl(
        file.name,
        file.type || 'application/pdf',
        projectId
      );

      // Upload file directly to storage
      const xhr = new XMLHttpRequest();
      
      await new Promise<void>((resolve, reject) => {
        xhr.upload.onprogress = (event) => {
          if (event.lengthComputable) {
            const progress = Math.round((event.loaded / event.total) * 100);
            setUploads(prev =>
              prev.map(u =>
                u.file.name === file.name
                  ? { ...u, progress, status: 'uploading' }
                  : u
              )
            );
          }
        };

        xhr.onload = () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve();
          } else {
            reject(new Error(`Upload failed: ${xhr.status}`));
          }
        };

        xhr.onerror = () => reject(new Error('Upload failed'));
        xhr.open('PUT', upload_url);
        xhr.setRequestHeader('Content-Type', file.type || 'application/pdf');
        xhr.send(file);
      });

      // Update status to complete
      // Use s3:// prefix for MinIO storage (local dev)
      const uri = `s3://overlay-uploads/${remote_path}`;
      setUploads(prev =>
        prev.map(u =>
          u.file.name === file.name
            ? { ...u, progress: 100, status: 'complete', uri }
            : u
        )
      );

      return uri;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Upload failed';
      setUploads(prev =>
        prev.map(u =>
          u.file.name === file.name
            ? { ...u, status: 'error', error: errorMessage }
            : u
        )
      );
      throw error;
    }
  }, [projectId]);

  const uploadFiles = useCallback(async (files: File[]): Promise<string[]> => {
    const results = await Promise.all(files.map(uploadFile));
    return results;
  }, [uploadFile]);

  const clearUploads = useCallback(() => {
    setUploads([]);
  }, []);

  const removeUpload = useCallback((filename: string) => {
    setUploads(prev => prev.filter(u => u.file.name !== filename));
  }, []);

  return {
    uploads,
    uploadFile,
    uploadFiles,
    clearUploads,
    removeUpload,
    isUploading: uploads.some(u => u.status === 'uploading'),
  };
}

export function useCreateDrawingWithUpload() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      projectId,
      file,
      name,
    }: {
      projectId: string;
      file: File;
      name?: string;
    }) => {
      // Use direct upload (more reliable than presigned URLs)
      const uploadResult = await api.uploads.uploadDirect(file, projectId);

      // Create drawing record with the URI returned from direct upload
      const drawing = await api.drawings.create({
        project_id: projectId,
        filename: file.name,
        name: name || file.name.replace(/\.[^/.]+$/, ''),
        uri: uploadResult.uri,
      });

      return drawing;
    },
    onSuccess: (_, { projectId }) => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId, 'drawings'] });
    },
  });
}

