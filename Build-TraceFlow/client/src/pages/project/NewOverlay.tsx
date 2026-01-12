import { useState, useCallback, useRef, useEffect } from "react";
import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Progress } from "@/components/ui/progress";
import { useLocation, useParams } from "wouter";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Upload, 
  ArrowRight, 
  ArrowLeft,
  FileText, 
  CheckCircle2,
  Loader2,
  Sparkles,
  MousePointer2,
  FolderOpen,
  Layers,
  Bot,
  AlertCircle,
  X,
  RefreshCw
} from "lucide-react";
import { useDrawings, useBlocks, useDrawingStatus } from "@/hooks/use-drawings";
import { useCreateComparison } from "@/hooks/use-comparison";
import { useCreateDrawingWithUpload } from "@/hooks/use-upload";
import { useToast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";
import logo from "@assets/BuildTrace_Logo_1767832159404.jpg";

// NEW WIZARD V2 - 3-stage comparison flow with URL state persistence
export default function NewOverlay() {
  const params = useParams<{ id: string }>();
  const projectId = params.id || "1";
  console.log("NewOverlay V2 - 3 Stage Wizard Loaded");
  const [location, setLocation] = useLocation();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Parse URL search params for state persistence
  const searchParams = new URLSearchParams(window.location.search);
  const initialStep = parseInt(searchParams.get('step') || '1', 10);
  const initialSourceDrawing = searchParams.get('source');
  const initialTargetDrawing = searchParams.get('target');
  const initialSourceMethod = searchParams.get('sm') as "existing" | "upload" | null;
  const initialTargetMethod = searchParams.get('tm') as "existing" | "upload" | null;

  // Wizard state - initialized from URL params
  const [step, setStepState] = useState(initialStep);
  const totalSteps = 3;
  const progress = (step / totalSteps) * 100;

  // Update URL when step changes
  const setStep = (newStep: number) => {
    setStepState(newStep);
    const url = new URL(window.location.href);
    url.searchParams.set('step', newStep.toString());
    window.history.replaceState({}, '', url.toString());
  };

  // Step 1: Drawing source selection
  const [sourceMethod, setSourceMethodState] = useState<"existing" | "upload" | null>(initialSourceMethod);
  const [targetMethod, setTargetMethodState] = useState<"existing" | "upload" | null>(initialTargetMethod);

  // Step 2: Block and matching mode selection
  const [overlayMode, setOverlayMode] = useState<"auto" | "manual">("auto");
  const [selectedSourceBlock, setSelectedSourceBlock] = useState<string | null>(null);
  const [selectedTargetBlock, setSelectedTargetBlock] = useState<string | null>(null);

  // Uploaded drawing IDs - initialized from URL params
  const [uploadedSourceDrawingId, setUploadedSourceDrawingIdState] = useState<string | null>(initialSourceDrawing);
  const [uploadedTargetDrawingId, setUploadedTargetDrawingIdState] = useState<string | null>(initialTargetDrawing);

  // Wrapper functions to update URL when drawing IDs change
  const setSourceMethod = (method: "existing" | "upload" | null) => {
    setSourceMethodState(method);
    const url = new URL(window.location.href);
    if (method) url.searchParams.set('sm', method);
    else url.searchParams.delete('sm');
    window.history.replaceState({}, '', url.toString());
  };

  const setTargetMethod = (method: "existing" | "upload" | null) => {
    setTargetMethodState(method);
    const url = new URL(window.location.href);
    if (method) url.searchParams.set('tm', method);
    else url.searchParams.delete('tm');
    window.history.replaceState({}, '', url.toString());
  };

  const setUploadedSourceDrawingId = (id: string | null) => {
    setUploadedSourceDrawingIdState(id);
    const url = new URL(window.location.href);
    if (id) url.searchParams.set('source', id);
    else url.searchParams.delete('source');
    window.history.replaceState({}, '', url.toString());
  };

  const setUploadedTargetDrawingId = (id: string | null) => {
    setUploadedTargetDrawingIdState(id);
    const url = new URL(window.location.href);
    if (id) url.searchParams.set('target', id);
    else url.searchParams.delete('target');
    window.history.replaceState({}, '', url.toString());
  };

  // File input refs
  const sourceFileInputRef = useRef<HTMLInputElement>(null);
  const targetFileInputRef = useRef<HTMLInputElement>(null);

  // API hooks
  const { data: drawings, isLoading: drawingsLoading } = useDrawings(projectId);
  const { data: allBlocks, isLoading: blocksLoading, refetch: refetchBlocks } = useBlocks("Plan");
  const createComparison = useCreateComparison();
  const createDrawingWithUpload = useCreateDrawingWithUpload();

  // Poll for drawing processing status
  const { data: sourceDrawingStatus, isLoading: sourceStatusLoading } = useDrawingStatus(uploadedSourceDrawingId || undefined);
  const { data: targetDrawingStatus, isLoading: targetStatusLoading } = useDrawingStatus(uploadedTargetDrawingId || undefined);

  // Use real blocks from API
  const availableBlocks = allBlocks && allBlocks.length > 0
    ? allBlocks.map(b => ({
        id: b.id,
        name: b.description || b.type || "Block",
        type: b.type || "Plan",
        uri: b.uri,
        date: new Date(b.created_at).toLocaleDateString(),
      }))
    : [];

  // Blocks from uploaded drawings
  const sourceBlocks = sourceDrawingStatus?.blocks?.filter(b => b.type === 'Plan') || [];
  const targetBlocks = targetDrawingStatus?.blocks?.filter(b => b.type === 'Plan') || [];

  // Auto-select first Plan block when available
  useEffect(() => {
    if (sourceDrawingStatus?.status === 'completed' && sourceBlocks.length > 0 && !selectedSourceBlock) {
      setSelectedSourceBlock(sourceBlocks[0].id);
        toast({
          title: "Processing Complete",
        description: `Found ${sourceBlocks.length} plan blocks in source drawing`,
        });
      }
  }, [sourceDrawingStatus, sourceBlocks.length]);

  useEffect(() => {
    if (targetDrawingStatus?.status === 'completed' && targetBlocks.length > 0 && !selectedTargetBlock) {
      setSelectedTargetBlock(targetBlocks[0].id);
        toast({
          title: "Processing Complete",
        description: `Found ${targetBlocks.length} plan blocks in compare drawing`,
      });
    }
  }, [targetDrawingStatus, targetBlocks.length]);

  // Handle file upload
  const handleFileUpload = async (file: File, type: 'source' | 'target') => {
    try {
      const drawing = await createDrawingWithUpload.mutateAsync({
        projectId,
        file,
        name: file.name.replace(/\.[^/.]+$/, ''),
      });

      if (type === 'source') {
        setUploadedSourceDrawingId(drawing.id);
        setSourceMethod("upload");
      } else {
        setUploadedTargetDrawingId(drawing.id);
        setTargetMethod("upload");
      }

      toast({
        title: "Upload Complete",
        description: `${file.name} has been uploaded. Processing blocks...`,
      });
    } catch (error) {
      toast({
        title: "Upload Failed",
        description: error instanceof Error ? error.message : "Failed to upload file",
        variant: "destructive",
      });
    }
  };

  const handleFileDrop = (e: React.DragEvent<HTMLDivElement>, type: 'source' | 'target') => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    if (files.length > 0) {
      handleFileUpload(files[0], type);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>, type: 'source' | 'target') => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0], type);
    }
  };

  // Navigation
  const handleNext = () => {
    if (step < totalSteps) {
      setStep(step + 1);
    }
  };

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1);
    }
  };

  // Determine if we can proceed to next step
  const canProceedStep1 = () => {
    const sourceReady = (sourceMethod === "existing" && selectedSourceBlock) || 
                        (sourceMethod === "upload" && uploadedSourceDrawingId);
    const targetReady = (targetMethod === "existing" && selectedTargetBlock) || 
                        (targetMethod === "upload" && uploadedTargetDrawingId);
    return sourceReady && targetReady;
  };

  const canProceedStep2 = () => {
    // Need both blocks selected (either from existing or from processed uploads)
    const sourceBlockReady = selectedSourceBlock || 
                            (sourceMethod === "upload" && sourceDrawingStatus?.status === 'completed' && sourceBlocks.length > 0);
    const targetBlockReady = selectedTargetBlock || 
                            (targetMethod === "upload" && targetDrawingStatus?.status === 'completed' && targetBlocks.length > 0);
    return sourceBlockReady && targetBlockReady;
  };

  // Check if uploads are still processing
  const isProcessingUploads = () => {
    const sourceProcessing = sourceMethod === "upload" && 
                            uploadedSourceDrawingId && 
                            (sourceDrawingStatus?.status === 'processing' || sourceDrawingStatus?.status === 'pending');
    const targetProcessing = targetMethod === "upload" && 
                            uploadedTargetDrawingId && 
                            (targetDrawingStatus?.status === 'processing' || targetDrawingStatus?.status === 'pending');
    return sourceProcessing || targetProcessing;
  };

  // Start the comparison
  const handleStartComparison = async () => {
    const sourceBlock = selectedSourceBlock || (sourceBlocks.length > 0 ? sourceBlocks[0].id : null);
    const targetBlock = selectedTargetBlock || (targetBlocks.length > 0 ? targetBlocks[0].id : null);

    if (!sourceBlock || !targetBlock) {
      toast({
        title: "Missing Blocks",
        description: "Please select blocks from both drawings to compare.",
        variant: "destructive",
      });
      return;
    }

    try {
      const result = await createComparison.mutateAsync({
        project_id: projectId,
        drawing_a_id: uploadedSourceDrawingId || '',
        drawing_b_id: uploadedTargetDrawingId || '',
        sheet_a_id: sourceBlock,
        sheet_b_id: targetBlock,
    });
    
    toast({
        title: "Comparison Started",
        description: "Generating overlay and analyzing changes...",
      });

      // Navigate to overlay viewer
      setLocation(`/project/${projectId}/overlay?comparison=${result.id}`);
    } catch (error) {
      toast({
        title: "Failed to Start Comparison",
        description: error instanceof Error ? error.message : "An error occurred",
        variant: "destructive",
      });
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header with Progress */}
      <header className="h-16 border-b border-border flex items-center px-8 bg-background/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center gap-2 mr-8 cursor-pointer" onClick={() => setLocation(`/project/${projectId}`)}>
          <img src={logo} alt="BuildTrace" className="w-8 h-8 rounded-md" />
          <span className="font-bold font-display">BuildTrace</span>
        </div>
        <div className="flex-1 max-w-md">
          <div className="flex justify-between text-xs font-medium text-muted-foreground mb-2">
            <span>New Comparison</span>
            <span>Step {step} of {totalSteps}</span>
          </div>
          <Progress value={progress} className="h-1.5" />
        </div>
        <Button variant="ghost" size="sm" className="ml-auto" onClick={() => setLocation(`/project/${projectId}`)}>
          <X className="w-4 h-4 mr-2" /> Cancel
        </Button>
      </header>

      {/* Step Indicators */}
      <div className="border-b border-border bg-muted/20 py-4">
        <div className="max-w-4xl mx-auto px-8">
          <div className="flex items-center justify-between">
            {[
              { num: 1, title: "Select Drawings", desc: "Upload or choose existing" },
              { num: 2, title: "Select Blocks & Mode", desc: "Choose matching method" },
              { num: 3, title: "Generate Overlay", desc: "Process and analyze" },
            ].map((s, i) => (
              <div key={s.num} className="flex items-center">
                <div className={`flex items-center gap-3 ${step >= s.num ? 'opacity-100' : 'opacity-50'}`}>
                  <div className={`w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold transition-colors ${
                    step > s.num ? 'bg-green-500 text-white' :
                    step === s.num ? 'bg-primary text-primary-foreground' :
                    'bg-muted text-muted-foreground'
                  }`}>
                    {step > s.num ? <CheckCircle2 className="w-5 h-5" /> : s.num}
                  </div>
                  <div>
                    <p className="font-medium text-sm">{s.title}</p>
                    <p className="text-xs text-muted-foreground">{s.desc}</p>
                  </div>
                </div>
                {i < 2 && (
                  <div className={`w-24 h-0.5 mx-4 transition-colors ${step > s.num ? 'bg-green-500' : 'bg-border'}`} />
                )}
              </div>
            ))}
                  </div>
                  </div>
                </div>

      {/* Main Content */}
      <main className="flex-1 py-8 px-8">
        <div className="max-w-4xl mx-auto">
          <AnimatePresence mode="wait">
            {/* Step 1: Select Drawing Source */}
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="space-y-6"
              >
                <div className="text-center mb-8">
                  <h1 className="text-2xl font-bold font-display">Select Drawings to Compare</h1>
                  <p className="text-muted-foreground mt-2">Upload new drawings or select from existing sets</p>
              </div>

        <div className="grid md:grid-cols-2 gap-6">
                  {/* Source Drawing */}
                  <Card className="border-2 border-dashed hover:border-primary/50 transition-colors">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-red-100 text-red-600 flex items-center justify-center text-xs font-bold">1</div>
                  Base Drawing
                </CardTitle>
                <Badge variant="outline" className="text-red-600 border-red-200">Previous</Badge>
              </div>
              <CardDescription>Select the original/older version</CardDescription>
            </CardHeader>
                    <CardContent className="space-y-4">
                      {/* Method Selection */}
                      <div className="grid grid-cols-2 gap-3">
                        <div 
                          onClick={() => { setSourceMethod("existing"); setUploadedSourceDrawingId(null); setSelectedSourceBlock(null); }}
                          className={`p-4 rounded-xl border-2 cursor-pointer transition-all text-center ${
                            sourceMethod === "existing" ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
                          }`}
                        >
                          <FolderOpen className="w-6 h-6 mx-auto mb-2 text-primary" />
                          <p className="font-medium text-sm">Existing Set</p>
                          <p className="text-xs text-muted-foreground">From library</p>
                        </div>
                        <div 
                          onClick={() => { setSourceMethod("upload"); setSelectedSourceBlock(null); }}
                          className={`p-4 rounded-xl border-2 cursor-pointer transition-all text-center ${
                            sourceMethod === "upload" ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
                          }`}
                        >
                          <Upload className="w-6 h-6 mx-auto mb-2 text-primary" />
                          <p className="font-medium text-sm">Upload New</p>
                          <p className="text-xs text-muted-foreground">PDF, DWG, DXF</p>
                        </div>
                      </div>

                      {/* Existing Set Selection */}
                      {sourceMethod === "existing" && (
                        <div className="animate-in slide-in-from-top-2 space-y-2">
                          <Label className="text-xs font-medium text-muted-foreground uppercase">Select Block</Label>
                          <ScrollArea className="h-[180px] border border-border rounded-lg">
                        <div className="p-2 space-y-1">
                              {availableBlocks.length > 0 ? availableBlocks.map((block) => (
                            <div 
                              key={block.id}
                                  onClick={() => setSelectedSourceBlock(block.id)}
                              className={`p-3 rounded-md cursor-pointer transition-all text-sm ${
                                    selectedSourceBlock === block.id 
                                  ? 'bg-red-50 border-2 border-red-300 dark:bg-red-900/20 dark:border-red-700' 
                                  : 'hover:bg-muted/50 border border-transparent'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-medium">{block.name}</span>
                                <Badge variant="outline" className="text-[10px] h-4">{block.type}</Badge>
                              </div>
                            </div>
                              )) : (
                                <div className="p-4 text-center text-muted-foreground text-sm">
                                  <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                  <p>No blocks available</p>
                                  <p className="text-xs mt-1">Upload a drawing first</p>
                    </div>
                  )}
                        </div>
                      </ScrollArea>
                    </div>
                  )}

                      {/* Upload Area */}
                      {sourceMethod === "upload" && (
                        <div className="animate-in slide-in-from-top-2 space-y-3">
                  <input
                    ref={sourceFileInputRef}
                    type="file"
                    accept=".pdf,.dwg,.dxf"
                    className="hidden"
                    onChange={(e) => handleFileSelect(e, 'source')}
                  />
                  
                          {!uploadedSourceDrawingId ? (
                    <div 
                      className="border-2 border-dashed border-border rounded-xl p-6 text-center hover:border-primary/50 transition-all cursor-pointer"
                      onClick={() => sourceFileInputRef.current?.click()}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => handleFileDrop(e, 'source')}
                    >
                      {createDrawingWithUpload.isPending ? (
                        <>
                          <Loader2 className="w-8 h-8 mx-auto mb-2 text-primary animate-spin" />
                          <p className="font-medium text-sm">Uploading...</p>
                        </>
                      ) : (
                        <>
                          <Upload className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
                          <p className="font-medium text-sm">Drop files or click to upload</p>
                          <p className="text-xs text-muted-foreground mt-1">PDF, DWG, DXF</p>
                        </>
                      )}
                    </div>
                          ) : (
                            <div className="p-4 rounded-lg border bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800">
                        <div className="flex items-center gap-2">
                            <CheckCircle2 className="w-5 h-5 text-green-600" />
                                <span className="font-medium text-sm text-green-700 dark:text-green-400">File uploaded successfully</span>
                        </div>
                              <p className="text-xs text-muted-foreground mt-1">Will be processed in step 3</p>
                        </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>

                  {/* Target Drawing */}
                  <Card className="border-2 border-dashed hover:border-primary/50 transition-colors">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg flex items-center gap-2">
                  <div className="w-6 h-6 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold">2</div>
                  Compare Drawing
                </CardTitle>
                <Badge variant="outline" className="text-green-600 border-green-200">Current</Badge>
              </div>
                      <CardDescription>Select the newer version to compare</CardDescription>
            </CardHeader>
                    <CardContent className="space-y-4">
                      {/* Method Selection */}
                      <div className="grid grid-cols-2 gap-3">
                        <div 
                          onClick={() => { setTargetMethod("existing"); setUploadedTargetDrawingId(null); setSelectedTargetBlock(null); }}
                          className={`p-4 rounded-xl border-2 cursor-pointer transition-all text-center ${
                            targetMethod === "existing" ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
                          }`}
                        >
                          <FolderOpen className="w-6 h-6 mx-auto mb-2 text-primary" />
                          <p className="font-medium text-sm">Existing Set</p>
                          <p className="text-xs text-muted-foreground">From library</p>
                        </div>
                        <div 
                          onClick={() => { setTargetMethod("upload"); setSelectedTargetBlock(null); }}
                          className={`p-4 rounded-xl border-2 cursor-pointer transition-all text-center ${
                            targetMethod === "upload" ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
                          }`}
                        >
                          <Upload className="w-6 h-6 mx-auto mb-2 text-primary" />
                          <p className="font-medium text-sm">Upload New</p>
                          <p className="text-xs text-muted-foreground">PDF, DWG, DXF</p>
                        </div>
                      </div>

                      {/* Existing Set Selection */}
                      {targetMethod === "existing" && (
                        <div className="animate-in slide-in-from-top-2 space-y-2">
                          <Label className="text-xs font-medium text-muted-foreground uppercase">Select Block</Label>
                          <ScrollArea className="h-[180px] border border-border rounded-lg">
                        <div className="p-2 space-y-1">
                              {availableBlocks.length > 0 ? availableBlocks.map((block) => (
                            <div 
                              key={block.id}
                                  onClick={() => setSelectedTargetBlock(block.id)}
                              className={`p-3 rounded-md cursor-pointer transition-all text-sm ${
                                    selectedTargetBlock === block.id 
                                  ? 'bg-green-50 border-2 border-green-300 dark:bg-green-900/20 dark:border-green-700' 
                                  : 'hover:bg-muted/50 border border-transparent'
                              }`}
                            >
                              <div className="flex items-center justify-between">
                                <span className="font-medium">{block.name}</span>
                                <Badge variant="outline" className="text-[10px] h-4">{block.type}</Badge>
                              </div>
                            </div>
                              )) : (
                                <div className="p-4 text-center text-muted-foreground text-sm">
                                  <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                                  <p>No blocks available</p>
                                  <p className="text-xs mt-1">Upload a drawing first</p>
                    </div>
                  )}
                        </div>
                      </ScrollArea>
                    </div>
                  )}

                      {/* Upload Area */}
                      {targetMethod === "upload" && (
                        <div className="animate-in slide-in-from-top-2 space-y-3">
                  <input
                    ref={targetFileInputRef}
                    type="file"
                    accept=".pdf,.dwg,.dxf"
                    className="hidden"
                    onChange={(e) => handleFileSelect(e, 'target')}
                  />
                  
                          {!uploadedTargetDrawingId ? (
                    <div 
                      className="border-2 border-dashed border-border rounded-xl p-6 text-center hover:border-primary/50 transition-all cursor-pointer"
                      onClick={() => targetFileInputRef.current?.click()}
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => handleFileDrop(e, 'target')}
                    >
                      {createDrawingWithUpload.isPending ? (
                        <>
                          <Loader2 className="w-8 h-8 mx-auto mb-2 text-primary animate-spin" />
                          <p className="font-medium text-sm">Uploading...</p>
                        </>
                      ) : (
                        <>
                          <Upload className="w-8 h-8 mx-auto mb-2 text-muted-foreground" />
                          <p className="font-medium text-sm">Drop files or click to upload</p>
                          <p className="text-xs text-muted-foreground mt-1">PDF, DWG, DXF</p>
                        </>
                      )}
                    </div>
                          ) : (
                            <div className="p-4 rounded-lg border bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800">
                              <div className="flex items-center gap-2">
                                <CheckCircle2 className="w-5 h-5 text-green-600" />
                                <span className="font-medium text-sm text-green-700 dark:text-green-400">File uploaded successfully</span>
                              </div>
                              <p className="text-xs text-muted-foreground mt-1">Will be processed in step 3</p>
                            </div>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                </div>
              </motion.div>
            )}

            {/* Step 2: Block Selection & Matching Mode */}
            {step === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="space-y-6"
              >
                <div className="text-center mb-8">
                  <h1 className="text-2xl font-bold font-display">Select Blocks & Matching Mode</h1>
                  <p className="text-muted-foreground mt-2">Choose which blocks to compare and how to match them</p>
                </div>

                {/* Block Selection for Uploaded Drawings */}
                {(sourceMethod === "upload" || targetMethod === "upload") && (
                  <div className="grid md:grid-cols-2 gap-6 mb-6">
                    {/* Source Blocks */}
                    {sourceMethod === "upload" && (
                      <Card>
                        <CardHeader className="pb-3">
                          <CardTitle className="text-lg flex items-center gap-2">
                            <div className="w-6 h-6 rounded-full bg-red-100 text-red-600 flex items-center justify-center text-xs font-bold">1</div>
                            Base Drawing Blocks
                          </CardTitle>
                          <CardDescription>
                            {sourceDrawingStatus?.status === 'completed' 
                              ? `${sourceBlocks.length} plan blocks extracted` 
                              : sourceDrawingStatus?.status === 'processing' || sourceDrawingStatus?.status === 'pending'
                              ? 'AI is extracting blocks...'
                              : 'Waiting...'}
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          {(sourceDrawingStatus?.status === 'processing' || sourceDrawingStatus?.status === 'pending') && (
                    <div className="space-y-3">
                        <div className="flex items-center gap-2">
                                <Loader2 className="w-4 h-4 animate-spin text-primary" />
                                <span className="text-sm">
                                  {(sourceDrawingStatus?.progress || 0) < 20 ? 'Converting PDF...' : 'Extracting blocks with AI...'}
                          </span>
                        </div>
                              <Progress value={sourceDrawingStatus?.progress || 5} />
                              <span className="text-xs text-muted-foreground">
                                {sourceDrawingStatus?.progress || 0}% complete
                              </span>
                            </div>
                          )}
                          
                          {sourceDrawingStatus?.status === 'completed' && sourceBlocks.length > 0 && (
                            <ScrollArea className="h-[200px]">
                              <div className="space-y-2">
                                {sourceBlocks.map((block) => (
                                  <div
                                    key={block.id}
                                    onClick={() => setSelectedSourceBlock(block.id)}
                                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                                      selectedSourceBlock === block.id
                                        ? 'border-red-500 bg-red-50 dark:bg-red-900/20'
                                        : 'border-border hover:border-red-300'
                                    }`}
                                  >
                                    <div className="flex items-center justify-between">
                                      <span className="font-medium text-sm">{block.description || block.type}</span>
                                      <Badge variant="outline" className="text-xs">{block.type}</Badge>
                      </div>
                                  </div>
                                ))}
                              </div>
                            </ScrollArea>
                          )}

                          {sourceDrawingStatus?.status === 'failed' && (
                            <div className="p-4 text-center text-red-600">
                              <AlertCircle className="w-8 h-8 mx-auto mb-2" />
                              <p className="text-sm">Processing failed</p>
                            </div>
                          )}
                        </CardContent>
                      </Card>
                    )}

                    {/* Target Blocks */}
                    {targetMethod === "upload" && (
                      <Card>
                        <CardHeader className="pb-3">
                          <CardTitle className="text-lg flex items-center gap-2">
                            <div className="w-6 h-6 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold">2</div>
                            Compare Drawing Blocks
                          </CardTitle>
                          <CardDescription>
                            {targetDrawingStatus?.status === 'completed' 
                              ? `${targetBlocks.length} plan blocks extracted` 
                              : targetDrawingStatus?.status === 'processing' || targetDrawingStatus?.status === 'pending'
                              ? 'AI is extracting blocks...'
                              : 'Waiting...'}
                          </CardDescription>
                        </CardHeader>
                        <CardContent>
                          {(targetDrawingStatus?.status === 'processing' || targetDrawingStatus?.status === 'pending') && (
                            <div className="space-y-3">
                              <div className="flex items-center gap-2">
                                <Loader2 className="w-4 h-4 animate-spin text-primary" />
                                <span className="text-sm">
                                  {(targetDrawingStatus?.progress || 0) < 20 ? 'Converting PDF...' : 'Extracting blocks with AI...'}
                                </span>
                              </div>
                              <Progress value={targetDrawingStatus?.progress || 5} />
                              <span className="text-xs text-muted-foreground">
                                {targetDrawingStatus?.progress || 0}% complete
                              </span>
                            </div>
                          )}
                          
                          {targetDrawingStatus?.status === 'completed' && targetBlocks.length > 0 && (
                            <ScrollArea className="h-[200px]">
                        <div className="space-y-2">
                                {targetBlocks.map((block) => (
                                <div 
                                  key={block.id}
                                  onClick={() => setSelectedTargetBlock(block.id)}
                                    className={`p-3 rounded-lg border cursor-pointer transition-all ${
                                    selectedTargetBlock === block.id 
                                        ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                                        : 'border-border hover:border-green-300'
                                  }`}
                                >
                                  <div className="flex items-center justify-between">
                                      <span className="font-medium text-sm">{block.description || block.type}</span>
                                      <Badge variant="outline" className="text-xs">{block.type}</Badge>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </ScrollArea>
                          )}

                          {targetDrawingStatus?.status === 'failed' && (
                            <div className="p-4 text-center text-red-600">
                              <AlertCircle className="w-8 h-8 mx-auto mb-2" />
                              <p className="text-sm">Processing failed</p>
                        </div>
                          )}
                        </CardContent>
                      </Card>
                      )}
                    </div>
                  )}

                {/* Matching Mode Selection */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Comparison Mode</CardTitle>
                    <CardDescription>Choose how you want to match and overlay drawings</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <div className="grid md:grid-cols-2 gap-4">
                      <div 
                        onClick={() => setOverlayMode("auto")}
                        className={`p-5 rounded-xl border-2 cursor-pointer transition-all ${
                          overlayMode === "auto" ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                            <Sparkles className="w-6 h-6 text-primary" />
                          </div>
                          <div>
                            <p className="font-semibold text-lg">Automatic Matching</p>
                            <p className="text-sm text-muted-foreground mt-1">
                              AI automatically aligns drawings using feature detection and overlays them precisely
                            </p>
                            <div className="flex gap-2 mt-3">
                              <Badge variant="secondary" className="text-xs">AI-Powered</Badge>
                              <Badge variant="secondary" className="text-xs">Recommended</Badge>
                            </div>
                          </div>
                        </div>
                      </div>

                      <div 
                        onClick={() => setOverlayMode("manual")}
                        className={`p-5 rounded-xl border-2 cursor-pointer transition-all ${
                          overlayMode === "manual" ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
                        }`}
                      >
                        <div className="flex items-start gap-3">
                          <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                            <MousePointer2 className="w-6 h-6 text-primary" />
                          </div>
                          <div>
                            <p className="font-semibold text-lg">Manual Selection</p>
                            <p className="text-sm text-muted-foreground mt-1">
                              Click corresponding points on each drawing to manually align them
                            </p>
                            <div className="flex gap-2 mt-3">
                              <Badge variant="outline" className="text-xs">Precise Control</Badge>
                              <Badge variant="outline" className="text-xs">6-Point</Badge>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>

              {/* Selection Summary */}
                <Card className="bg-muted/30 border-dashed">
                  <CardContent className="py-4">
                    <div className="flex items-center justify-center gap-8">
                      <div className="text-center">
                        <p className="text-xs text-red-500 uppercase tracking-wider mb-1">Base Drawing</p>
                        <p className="font-semibold text-sm">
                          {selectedSourceBlock 
                            ? (sourceMethod === "existing" 
                                ? availableBlocks.find(b => b.id === selectedSourceBlock)?.name 
                                : sourceBlocks.find(b => b.id === selectedSourceBlock)?.description || 'Selected')
                            : sourceMethod === "upload" ? "Processing..." : "Not selected"}
                        </p>
                </div>
                      <Layers className="w-5 h-5 text-muted-foreground" />
                      <div className="text-center">
                        <p className="text-xs text-green-500 uppercase tracking-wider mb-1">Compare Drawing</p>
                        <p className="font-semibold text-sm">
                          {selectedTargetBlock 
                            ? (targetMethod === "existing" 
                                ? availableBlocks.find(b => b.id === selectedTargetBlock)?.name 
                                : targetBlocks.find(b => b.id === selectedTargetBlock)?.description || 'Selected')
                            : targetMethod === "upload" ? "Processing..." : "Not selected"}
                        </p>
                      </div>
                      <div className="w-px h-8 bg-border" />
                      <div className="text-center">
                        <p className="text-xs text-muted-foreground uppercase tracking-wider mb-1">Mode</p>
                        <Badge variant="outline">{overlayMode === "auto" ? "Automatic" : "Manual"}</Badge>
                      </div>
                    </div>
            </CardContent>
          </Card>
              </motion.div>
            )}

            {/* Step 3: Processing & Results Preview */}
            {step === 3 && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="space-y-6"
              >
                <div className="text-center mb-8">
                  <h1 className="text-2xl font-bold font-display">Generate Overlay & Analyze Changes</h1>
                  <p className="text-muted-foreground mt-2">Review your selections and start the comparison</p>
        </div>

                {/* Processing Status for Uploads */}
                {isProcessingUploads() && (
                  <Card className="border-blue-200 bg-blue-50/50 dark:bg-blue-900/10">
          <CardContent className="py-6">
                      <div className="text-center space-y-4">
                        <div className="relative w-20 h-20 mx-auto">
                          <div className="w-20 h-20 rounded-full bg-blue-100 dark:bg-blue-900/30 flex items-center justify-center">
                            <Loader2 className="w-10 h-10 animate-spin text-blue-600" />
                          </div>
                          <div className="absolute inset-0 w-20 h-20 rounded-full border-4 border-blue-300/50 animate-ping" style={{ animationDuration: '2s' }} />
                        </div>
                        <div>
                          <h3 className="text-lg font-semibold text-blue-900 dark:text-blue-100">Processing Drawings</h3>
                          <p className="text-sm text-blue-700 dark:text-blue-300 mt-1">
                            AI is extracting blocks and preparing drawings for comparison...
                          </p>
                        </div>
                        <div className="flex justify-center gap-4">
                          {sourceMethod === "upload" && uploadedSourceDrawingId && (
                <div className="text-center">
                              <p className="text-xs text-muted-foreground">Base Drawing</p>
                              <Badge variant={sourceDrawingStatus?.status === 'completed' ? 'default' : 'outline'} className="mt-1">
                                {sourceDrawingStatus?.status === 'completed' ? <CheckCircle2 className="w-3 h-3 mr-1" /> : <RefreshCw className="w-3 h-3 mr-1 animate-spin" />}
                                {sourceDrawingStatus?.status || 'Pending'}
                              </Badge>
                            </div>
                          )}
                          {targetMethod === "upload" && uploadedTargetDrawingId && (
                            <div className="text-center">
                              <p className="text-xs text-muted-foreground">Compare Drawing</p>
                              <Badge variant={targetDrawingStatus?.status === 'completed' ? 'default' : 'outline'} className="mt-1">
                                {targetDrawingStatus?.status === 'completed' ? <CheckCircle2 className="w-3 h-3 mr-1" /> : <RefreshCw className="w-3 h-3 mr-1 animate-spin" />}
                                {targetDrawingStatus?.status || 'Pending'}
                              </Badge>
                            </div>
                          )}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Ready to Compare */}
                {!isProcessingUploads() && (
                  <Card className="border-green-200 bg-green-50/50 dark:bg-green-900/10">
                    <CardContent className="py-6">
                      <div className="text-center space-y-4">
                        <div className="w-16 h-16 mx-auto rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                          <CheckCircle2 className="w-8 h-8 text-green-600" />
                        </div>
                        <div>
                          <h3 className="text-lg font-semibold text-green-900 dark:text-green-100">Ready to Compare</h3>
                          <p className="text-sm text-green-700 dark:text-green-300 mt-1">
                            All drawings processed. Click below to generate the overlay.
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )}

                {/* Summary Card */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg">Comparison Summary</CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid md:grid-cols-3 gap-6">
                      <div className="p-4 rounded-lg bg-red-50 dark:bg-red-900/10 border border-red-200 dark:border-red-800">
                        <p className="text-xs text-red-500 uppercase tracking-wider font-medium mb-2">Base Drawing (Previous)</p>
                        <p className="font-semibold">
                          {selectedSourceBlock 
                            ? (sourceMethod === "existing" 
                                ? availableBlocks.find(b => b.id === selectedSourceBlock)?.name 
                                : sourceBlocks.find(b => b.id === selectedSourceBlock)?.description || 'Block Selected')
                            : "Pending..."}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {sourceMethod === "upload" ? "Uploaded file" : "From library"}
                        </p>
                </div>
                      
                      <div className="p-4 rounded-lg bg-green-50 dark:bg-green-900/10 border border-green-200 dark:border-green-800">
                        <p className="text-xs text-green-500 uppercase tracking-wider font-medium mb-2">Compare Drawing (Current)</p>
                  <p className="font-semibold">
                          {selectedTargetBlock 
                            ? (targetMethod === "existing" 
                                ? availableBlocks.find(b => b.id === selectedTargetBlock)?.name 
                                : targetBlocks.find(b => b.id === selectedTargetBlock)?.description || 'Block Selected')
                            : "Pending..."}
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {targetMethod === "upload" ? "Uploaded file" : "From library"}
                        </p>
                      </div>

                      <div className="p-4 rounded-lg bg-muted/30 border border-border">
                        <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium mb-2">Comparison Mode</p>
                        <div className="flex items-center gap-2">
                          {overlayMode === "auto" ? (
                            <Sparkles className="w-5 h-5 text-primary" />
                          ) : (
                            <MousePointer2 className="w-5 h-5 text-primary" />
                          )}
                          <p className="font-semibold">{overlayMode === "auto" ? "Automatic" : "Manual"}</p>
                </div>
                        <p className="text-xs text-muted-foreground mt-1">
                          {overlayMode === "auto" ? "AI-powered alignment" : "Click to align points"}
                        </p>
                </div>
              </div>
                  </CardContent>
                </Card>

                {/* What Happens Next */}
                <Card className="bg-muted/20">
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <Bot className="w-5 h-5 text-primary" />
                      What Happens Next
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="grid md:grid-cols-3 gap-4">
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0 text-sm font-bold text-primary">1</div>
                        <div>
                          <p className="font-medium text-sm">Overlay Generation</p>
                          <p className="text-xs text-muted-foreground">AI aligns and overlays the drawings</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0 text-sm font-bold text-primary">2</div>
                        <div>
                          <p className="font-medium text-sm">Change Detection</p>
                          <p className="text-xs text-muted-foreground">Automatically detect additions & deletions</p>
                        </div>
                      </div>
                      <div className="flex items-start gap-3">
                        <div className="w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center shrink-0 text-sm font-bold text-primary">3</div>
                        <div>
                          <p className="font-medium text-sm">AI Analysis</p>
                          <p className="text-xs text-muted-foreground">Cost & schedule impact assessment</p>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Navigation */}
          <div className="flex justify-between mt-8 pt-6 border-t border-border">
              <Button 
              variant="outline" 
              onClick={handleBack}
              disabled={step === 1}
                className="gap-2"
              >
              <ArrowLeft className="w-4 h-4" /> Back
            </Button>
            
            {step < totalSteps ? (
              <Button 
                onClick={handleNext} 
                disabled={
                  (step === 1 && !canProceedStep1()) ||
                  (step === 2 && !canProceedStep2())
                }
                className="gap-2 min-w-[140px]"
              >
                Continue <ArrowRight className="w-4 h-4" />
              </Button>
            ) : (
              <Button 
                onClick={handleStartComparison}
                disabled={isProcessingUploads() || createComparison.isPending || !selectedSourceBlock || !selectedTargetBlock}
                className="gap-2 min-w-[180px]"
              >
                {createComparison.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" /> Starting...
                  </>
                ) : (
                  <>
                    <Layers className="w-4 h-4" /> Generate Overlay
                  </>
                )}
              </Button>
            )}
            </div>
      </div>
      </main>
    </div>
  );
}
