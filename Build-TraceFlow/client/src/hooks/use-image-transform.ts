import { useState, useCallback, useRef, useEffect } from 'react';

export interface ImageTransform {
  scale: number;
  translateX: number;
  translateY: number;
}

export interface UseImageTransformOptions {
  minScale?: number;
  maxScale?: number;
  zoomStep?: number;
}

export function useImageTransform(options: UseImageTransformOptions = {}) {
  const {
    minScale = 0.5,
    maxScale = 5,
    zoomStep = 0.25,
  } = options;

  const [transform, setTransform] = useState<ImageTransform>({
    scale: 1,
    translateX: 0,
    translateY: 0,
  });

  const [isPanning, setIsPanning] = useState(false);
  const [panMode, setPanMode] = useState(false);
  const lastMousePos = useRef({ x: 0, y: 0 });

  // Zoom in function
  const zoomIn = useCallback(() => {
    setTransform(prev => ({
      ...prev,
      scale: Math.min(prev.scale + zoomStep, maxScale),
    }));
  }, [zoomStep, maxScale]);

  // Zoom out function
  const zoomOut = useCallback(() => {
    setTransform(prev => ({
      ...prev,
      scale: Math.max(prev.scale - zoomStep, minScale),
    }));
  }, [zoomStep, minScale]);

  // Reset transform
  const resetTransform = useCallback(() => {
    setTransform({
      scale: 1,
      translateX: 0,
      translateY: 0,
    });
  }, []);

  // Zoom to specific scale
  const zoomTo = useCallback((scale: number) => {
    setTransform(prev => ({
      ...prev,
      scale: Math.max(minScale, Math.min(scale, maxScale)),
    }));
  }, [minScale, maxScale]);

  // Handle mouse down for panning
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    if (!panMode) return;
    setIsPanning(true);
    lastMousePos.current = { x: e.clientX, y: e.clientY };
  }, [panMode]);

  // Handle mouse move for panning
  const handleMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning || !panMode) return;

    const deltaX = e.clientX - lastMousePos.current.x;
    const deltaY = e.clientY - lastMousePos.current.y;

    setTransform(prev => ({
      ...prev,
      translateX: prev.translateX + deltaX,
      translateY: prev.translateY + deltaY,
    }));

    lastMousePos.current = { x: e.clientX, y: e.clientY };
  }, [isPanning, panMode]);

  // Handle mouse up for panning
  const handleMouseUp = useCallback(() => {
    setIsPanning(false);
  }, []);

  // Handle mouse wheel for zooming
  const handleWheel = useCallback((e: WheelEvent) => {
    if (!panMode) return;
    e.preventDefault();

    const delta = e.deltaY > 0 ? -zoomStep : zoomStep;
    setTransform(prev => ({
      ...prev,
      scale: Math.max(minScale, Math.min(prev.scale + delta, maxScale)),
    }));
  }, [panMode, zoomStep, minScale, maxScale]);

  // Enable/disable pan mode
  const togglePanMode = useCallback(() => {
    setPanMode(prev => !prev);
  }, []);

  // Get transform style
  const getTransformStyle = useCallback(() => {
    return {
      transform: `translate(${transform.translateX}px, ${transform.translateY}px) scale(${transform.scale})`,
      transformOrigin: 'center center',
      transition: isPanning ? 'none' : 'transform 0.2s ease-out',
      cursor: panMode ? (isPanning ? 'grabbing' : 'grab') : 'default',
    };
  }, [transform, isPanning, panMode]);

  // Add wheel event listener
  useEffect(() => {
    const handleWheelEvent = (e: WheelEvent) => {
      if (panMode) {
        handleWheel(e);
      }
    };

    document.addEventListener('wheel', handleWheelEvent, { passive: false });
    return () => {
      document.removeEventListener('wheel', handleWheelEvent);
    };
  }, [handleWheel, panMode]);

  return {
    transform,
    zoomIn,
    zoomOut,
    resetTransform,
    zoomTo,
    panMode,
    togglePanMode,
    isPanning,
    handleMouseDown,
    handleMouseMove,
    handleMouseUp,
    getTransformStyle,
  };
}
