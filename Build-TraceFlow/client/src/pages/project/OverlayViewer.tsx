import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Separator } from "@/components/ui/separator";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { 
  ZoomIn, 
  ZoomOut, 
  Move, 
  Layers, 
  Download, 
  Share2,
  Filter,
  DollarSign,
  MessageSquare,
  Send,
  Plus,
  X,
  Save,
  CalendarDays,
  Sparkles,
  MousePointer2,
  Target,
  RotateCcw,
  MessageCircle,
  Bot,
  Loader2,
  BarChart3,
  AlertCircle
} from "lucide-react";
import blueprint from "@assets/generated_images/architectural_floor_plan_blueprint.png";
import React, { useState, useMemo } from "react";
import { useParams, useSearch } from "wouter";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetFooter,
} from "@/components/ui/sheet";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import { useComparison, useChanges, useUpdateChange, useCreateChange, useCreateComparison } from "@/hooks/use-comparison";
import { useManualAlignment, createInitialAlignmentState, addAlignmentPoint, resetAlignmentPoints, type Point as AlignmentPoint } from "@/hooks/use-alignment";
import { useDrawingStatus } from "@/hooks/use-drawings";
import type { Change } from "@/lib/api";
import api from "@/lib/api";
import { useToast } from "@/hooks/use-toast";
import { useQueryClient } from "@tanstack/react-query";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";

// Mock data for demo mode (when API is unavailable)
const MOCK_CHANGES = [
  { id: "1", type: "removed" as const, title: "Wall Partition Moved", sheet: "A-101", discipline: "Architectural", cost: "$12,000", schedule: "+2 Days", trade: "Framing", status: "Open", assignee: "Mike Ross" },
  { id: "2", type: "added" as const, title: "New Door Added", sheet: "A-101", discipline: "Architectural", cost: "$2,500", schedule: "+1 Day", trade: "Doors", status: "In Review", assignee: "Sarah Chen" },
  { id: "3", type: "removed" as const, title: "Cabinet Removed", sheet: "A-101", discipline: "Architectural", cost: "-$1,200", schedule: "0 Days", trade: "Millwork", status: "Closed", assignee: "Unassigned" },
  { id: "4", type: "added" as const, title: "Duct Rerouted", sheet: "M-102", discipline: "Mechanical", cost: "$8,000", schedule: "+1 Day", trade: "HVAC", status: "Pricing", assignee: "Alex Morgan" },
  { id: "5", type: "added" as const, title: "Outlet Added", sheet: "E-101", discipline: "Electrical", cost: "$400", schedule: "0 Days", trade: "Electrical", status: "Open", assignee: "Unassigned" },
];

export default function OverlayViewer() {
  // Get project ID from URL params and query params
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const searchString = useSearch();
  const searchParams = new URLSearchParams(searchString);
  const comparisonId = searchParams.get('comparison');
  const sourceDrawingId = searchParams.get('source_drawing');
  const targetDrawingId = searchParams.get('target_drawing');
  
  // Block selection mode - when we have drawing IDs but no comparison yet
  const isBlockSelectionMode = !comparisonId && sourceDrawingId && targetDrawingId;
  
  // Polling for drawing status to get blocks
  const { data: sourceStatus } = useDrawingStatus(sourceDrawingId || undefined);
  const { data: targetStatus } = useDrawingStatus(targetDrawingId || undefined);
  
  // Selected blocks for comparison
  const [selectedSourceBlock, setSelectedSourceBlock] = useState<string | null>(null);
  const [selectedTargetBlock, setSelectedTargetBlock] = useState<string | null>(null);
  
  // Create comparison mutation
  const createComparison = useCreateComparison();

  // Fetch comparison and changes from API
  const { data: comparison, isLoading: comparisonLoading } = useComparison(comparisonId || undefined);
  const { data: apiChanges, isLoading: changesLoading } = useChanges(comparisonId || undefined);
  const updateChangeMutation = useUpdateChange();
  const createChangeMutation = useCreateChange(comparisonId || '');

  // AI Analysis state - must be declared before changes memo
  const [aiDetectedChanges, setAiDetectedChanges] = useState<Array<{
    id: string;
    type: string;
    title: string;
    description?: string;
    trade?: string;
    discipline?: string;
    estimated_cost?: string;
    schedule_impact?: string;
    confidence?: number;
  }>>([]);
  const [analysisSummary, setAnalysisSummary] = useState<{
    total_cost_impact?: string;
    total_schedule_impact?: string;
    biggest_cost_driver?: string;
    analysis_summary?: string;
  } | null>(null);

  // Use API data merged with AI-detected changes
  const changes = useMemo(() => {
    // First, check for AI-detected changes (from overlay analysis)
    if (aiDetectedChanges && aiDetectedChanges.length > 0) {
      return aiDetectedChanges.map((c, index) => ({
        id: c.id || `ai-${index}`,
        type: c.type === 'added' ? 'new' : c.type === 'removed' ? 'deleted' : c.type,
        title: c.title,
        sheet: 'A-101',
        discipline: c.discipline || 'Architectural',
        cost: c.estimated_cost || '$0',
        schedule: c.schedule_impact || '0 Days',
        trade: c.trade || 'General',
        status: 'Open',
        assignee: 'Unassigned',
      }));
    }
    // Fall back to API changes from comparison endpoint
    if (apiChanges && apiChanges.length > 0) {
      return apiChanges.map((c: Change) => ({
        id: c.id,
        type: c.type === 'added' ? 'new' : c.type === 'removed' ? 'deleted' : c.type,
        title: c.title,
        sheet: c.description?.split(' ')[0] || 'A-101',
        discipline: c.discipline || 'Architectural',
        cost: c.estimated_cost || '$0',
        schedule: c.schedule_impact || '0 Days',
        trade: c.trade || 'General',
        status: c.status === 'open' ? 'Open' : c.status === 'in_review' ? 'In Review' : c.status,
        assignee: c.assignee || 'Unassigned',
      }));
    }
    // Return empty array when no changes detected
    return [];
  }, [apiChanges, aiDetectedChanges]);

  // Overlay image - use API data if available
  const overlayImage = comparison?.overlay_uri || blueprint;

  const [activeChangeId, setActiveChangeId] = useState<string | null>(null);
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  const [viewMode, setViewMode] = useState<"overlay" | "sidebyside">("overlay");
  const [isAddingChange, setIsAddingChange] = useState(false);
  const [showAddDialog, setShowAddDialog] = useState(false);
  
  // Determine comparison status - use actual API status
  const isProcessing = comparison?.status === 'processing';
  const isCompleted = comparison?.status === 'completed';
  const isFailed = comparison?.status === 'failed';
  
  // Show changes when comparison is completed and we have the overlay
  const [showChanges, setShowChanges] = useState(false);
  
  // Update showChanges when comparison completes
  React.useEffect(() => {
    if (isCompleted && comparison?.overlay_uri) {
      setShowChanges(true);
    }
  }, [isCompleted, comparison?.overlay_uri]);
  const [alignmentMode, setAlignmentMode] = useState(false);
  const [alignmentState, setAlignmentState] = useState(createInitialAlignmentState());
  const alignmentPoints = alignmentState.sourcePoints.length + alignmentState.targetPoints.length;
  const manualAlignmentMutation = useManualAlignment();
  const { toast } = useToast();
  const [chatOpen, setChatOpen] = useState(false);
  const [chatMessages, setChatMessages] = useState<{role: 'user' | 'assistant', content: string}[]>([
    { role: 'assistant', content: 'Hello! I\'m your BuildTrace AI assistant. I can help you analyze drawings, understand changes, or answer questions about your project. What would you like to know?' }
  ]);
  const [chatInput, setChatInput] = useState('');
  
  // AI Analysis state
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  
  // Function to run AI change detection
  const runAIAnalysis = async () => {
    if (!comparison?.id) {
      toast({
        title: "No overlay available",
        description: "Please wait for the overlay to be generated first.",
        variant: "destructive",
      });
      return;
    }
    
    // Get overlay ID - the comparison id is also used for overlay in some cases
    const overlayId = comparison.id;
    
    setIsAnalyzing(true);
    setAnalysisError(null);
    
    try {
      // Call the AI change detection API
      const result = await api.analysis.detectChanges(overlayId, true);
      
      toast({
        title: "AI Analysis Started",
        description: result.message || "Analyzing changes with AI...",
      });
      
      // Poll for results - the API returns immediately but processing takes time
      const pollForResults = async (attempts: number = 0) => {
        if (attempts >= 12) { // Max 60 seconds (12 * 5s)
          setIsAnalyzing(false);
          toast({
            title: "Analysis Taking Longer",
            description: "The analysis is still processing. Check back in a moment.",
          });
          return;
        }
        
        try {
          const summary = await api.analysis.getSummary(overlayId);
          if (summary.changes && summary.changes.length > 0) {
            // Store the AI-detected changes directly
            setAiDetectedChanges(summary.changes);
            setAnalysisSummary(summary.summary || null);
            setIsAnalyzing(false);
            
            toast({
              title: "Analysis Complete",
              description: `Detected ${summary.changes.length} changes with cost/schedule estimates.`,
            });
          } else {
            // Not ready yet, poll again
            setTimeout(() => pollForResults(attempts + 1), 5000);
          }
        } catch {
          // Not ready yet, poll again
          setTimeout(() => pollForResults(attempts + 1), 5000);
        }
      };
      
      // Start polling after initial delay
      setTimeout(() => pollForResults(0), 3000);
      
    } catch (error) {
      setIsAnalyzing(false);
      const errorMsg = error instanceof Error ? error.message : "Failed to run AI analysis";
      setAnalysisError(errorMsg);
      toast({
        title: "Analysis Failed",
        description: errorMsg,
        variant: "destructive",
      });
    }
  };
  
  // Load existing analysis results on mount
  React.useEffect(() => {
    const loadExistingAnalysis = async () => {
      if (!comparison?.id) return;
      try {
        const summary = await api.analysis.getSummary(comparison.id);
        if (summary.changes && summary.changes.length > 0) {
          setAiDetectedChanges(summary.changes);
          setAnalysisSummary(summary.summary || null);
        }
      } catch {
        // No existing analysis, that's fine
      }
    };
    loadExistingAnalysis();
  }, [comparison?.id]);

  const activeChange = changes.find(c => c.id === activeChangeId);

  const handleSelectChange = (id: string) => {
    setActiveChangeId(id);
    setIsSheetOpen(true);
  };

  const handleAlignmentClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!alignmentMode || alignmentState.isComplete) return;

    // Get click position relative to the overlay image
    const rect = e.currentTarget.getBoundingClientRect();
    const x = ((e.clientX - rect.left) / rect.width) * 1000; // Normalize to 0-1000
    const y = ((e.clientY - rect.top) / rect.height) * 1000;

    const newState = addAlignmentPoint(alignmentState, { x, y });
    setAlignmentState(newState);

    // When all 6 points are collected, submit the alignment
    if (newState.isComplete && comparisonId) {
      manualAlignmentMutation.mutate(
        {
          overlay_id: comparisonId,
          source_points: newState.sourcePoints,
          target_points: newState.targetPoints,
        },
        {
          onSuccess: (data) => {
            toast({
              title: "Manual Alignment Submitted",
              description: `Scale: ${data.scale?.toFixed(2)}x, Rotation: ${data.rotation_deg?.toFixed(1)}°`,
            });
            setAlignmentMode(false);
            setAlignmentState(resetAlignmentPoints());
          },
          onError: (error) => {
            toast({
              title: "Alignment Failed",
              description: error.message,
              variant: "destructive",
            });
          },
        }
      );
    }
  };

  const handleSendMessage = () => {
    if (!chatInput.trim()) return;
    setChatMessages(prev => [...prev, { role: 'user', content: chatInput }]);
    const userMsg = chatInput;
    setChatInput('');
    
    setTimeout(() => {
      setChatMessages(prev => [...prev, { 
        role: 'assistant', 
        content: `Based on the current overlay comparison, I can see that ${userMsg.toLowerCase().includes('change') ? 'there are 5 detected changes between Bulletin 02 and Bulletin 03, with a total estimated cost impact of $21,700.' : 'the drawings show modifications primarily in the architectural and mechanical disciplines. Would you like me to provide more specific details about any particular area?'}`
      }]);
    }, 1500);
  };

  const getChangeColor = (type: string) => {
    switch(type) {
      case 'new': return { border: 'border-green-500', bg: 'bg-green-500/20', text: 'text-green-600' };
      case 'deleted': return { border: 'border-red-500', bg: 'bg-red-500/20', text: 'text-red-600' };
      default: return { border: 'border-slate-400', bg: 'bg-slate-400/20', text: 'text-slate-500' };
    }
  };

  // Handle starting overlay comparison with selected blocks
  const handleStartOverlay = async () => {
    if (!selectedSourceBlock || !selectedTargetBlock) return;
    
    try {
      const result = await createComparison.mutateAsync({
        project_id: projectId || '123',
        drawing_a_id: sourceDrawingId || '',
        drawing_b_id: targetDrawingId || '',
        sheet_a_id: selectedSourceBlock,
        sheet_b_id: selectedTargetBlock,
      });
      
      // Navigate to the comparison view with the new comparison ID
      window.location.href = `/project/${projectId}/overlay?comparison=${result.id}`;
    } catch (error) {
      toast({
        title: "Failed to Start Overlay",
        description: error instanceof Error ? error.message : "An error occurred",
        variant: "destructive",
      });
    }
  };

  // Filter to get only Plan blocks (for overlay comparison)
  const sourceBlocks = sourceStatus?.blocks?.filter(b => b.type === 'Plan') || [];
  const targetBlocks = targetStatus?.blocks?.filter(b => b.type === 'Plan') || [];

  return (
    <DashboardLayout>
      <div className="h-[calc(100vh-4rem)] flex flex-col relative">
        
        {/* Block Selection Mode - when drawings are uploaded but blocks need to be selected */}
        {isBlockSelectionMode && (
          <div className="flex-1 p-8 overflow-auto">
            <div className="max-w-4xl mx-auto space-y-6">
              <div className="text-center mb-8">
                <h1 className="text-2xl font-bold">Select Blocks for Comparison</h1>
                <p className="text-muted-foreground mt-2">
                  Choose which blocks to overlay from each drawing
                </p>
              </div>

              <div className="grid md:grid-cols-2 gap-6">
                {/* Source Drawing Blocks */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-red-100 text-red-600 flex items-center justify-center text-xs font-bold">1</div>
                      Base Drawing (Old)
                    </CardTitle>
                    <CardDescription>
                      {sourceStatus?.status === 'completed' 
                        ? `${sourceBlocks.length} Plan blocks found` 
                        : sourceStatus?.status === 'processing' || sourceStatus?.status === 'pending'
                        ? 'Extracting blocks...'
                        : 'Waiting for processing...'}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {(sourceStatus?.status === 'processing' || sourceStatus?.status === 'pending') && (
                      <div className="space-y-3">
                        <div className="flex items-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin text-primary" />
                          <span className="text-sm">AI is extracting blocks...</span>
                        </div>
                        <Progress value={sourceStatus?.status === 'processing' ? 60 : 20} />
                      </div>
                    )}
                    
                    {sourceStatus?.status === 'completed' && sourceBlocks.length > 0 && (
                      <ScrollArea className="h-[250px]">
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
                    
                    {sourceStatus?.status === 'completed' && sourceBlocks.length === 0 && (
                      <p className="text-sm text-muted-foreground">No Plan blocks found in this drawing.</p>
                    )}
                  </CardContent>
                </Card>

                {/* Target Drawing Blocks */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-lg flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold">2</div>
                      Compare Drawing (New)
                    </CardTitle>
                    <CardDescription>
                      {targetStatus?.status === 'completed' 
                        ? `${targetBlocks.length} Plan blocks found` 
                        : targetStatus?.status === 'processing' || targetStatus?.status === 'pending'
                        ? 'Extracting blocks...'
                        : 'Waiting for processing...'}
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {(targetStatus?.status === 'processing' || targetStatus?.status === 'pending') && (
                      <div className="space-y-3">
                        <div className="flex items-center gap-2">
                          <Loader2 className="w-4 h-4 animate-spin text-primary" />
                          <span className="text-sm">AI is extracting blocks...</span>
                        </div>
                        <Progress value={targetStatus?.status === 'processing' ? 60 : 20} />
                      </div>
                    )}
                    
                    {targetStatus?.status === 'completed' && targetBlocks.length > 0 && (
                      <ScrollArea className="h-[250px]">
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
                    
                    {targetStatus?.status === 'completed' && targetBlocks.length === 0 && (
                      <p className="text-sm text-muted-foreground">No Plan blocks found in this drawing.</p>
                    )}
                  </CardContent>
                </Card>
              </div>

              {/* Start Overlay Button */}
              <div className="flex justify-center pt-4">
                <Button
                  size="lg"
                  disabled={!selectedSourceBlock || !selectedTargetBlock || createComparison.isPending}
                  onClick={handleStartOverlay}
                  className="gap-2 min-w-[200px]"
                >
                  {createComparison.isPending ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" /> Starting Overlay...
                    </>
                  ) : (
                    <>
                      <Layers className="w-4 h-4" /> Generate Overlay
                    </>
                  )}
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Regular Overlay Viewer - when we have a comparison ID */}
        {!isBlockSelectionMode && (
        <>
        {/* Toolbar */}
        <div className="h-14 border-b border-border bg-background px-4 flex items-center justify-between shrink-0">
          <div className="flex items-center gap-4">
             <div className="flex items-center gap-2">
               <span className="font-bold text-sm">A-101 First Floor Plan</span>
               <Badge variant="outline" className="text-[10px] h-5">{viewMode === "overlay" ? "Overlay" : "Side-by-Side"}</Badge>
             </div>
             <div className="h-4 w-[1px] bg-border" />
             <div className="flex items-center gap-1 bg-muted/50 p-1 rounded-md">
                <Button variant="ghost" size="icon" className="h-7 w-7"><ZoomIn className="w-4 h-4" /></Button>
                <Button variant="ghost" size="icon" className="h-7 w-7"><ZoomOut className="w-4 h-4" /></Button>
                <Button variant="ghost" size="icon" className="h-7 w-7"><Move className="w-4 h-4" /></Button>
             </div>
             <div className="h-4 w-[1px] bg-border" />
             
             {/* Manual Alignment */}
             <Button 
               variant={alignmentMode ? "default" : "outline"} 
               size="sm" 
               className="h-7 gap-1.5"
               onClick={() => {
                 if (!alignmentMode) {
                   setAlignmentMode(true);
                   setAlignmentState(resetAlignmentPoints());
                 } else {
                   setAlignmentMode(false);
                   setAlignmentState(resetAlignmentPoints());
                 }
               }}
             >
               <Target className="w-3 h-3" />
               {alignmentMode ? `Points: ${alignmentPoints}/6` : "Manual Align"}
             </Button>

             {alignmentMode && (
               <Button variant="ghost" size="sm" className="h-7 gap-1" onClick={() => { setAlignmentMode(false); setAlignmentState(resetAlignmentPoints()); }}>
                 <RotateCcw className="w-3 h-3" /> Reset
               </Button>
             )}

             {/* Show panel toggle when comparison is complete and has changes */}
             {isCompleted && changes.length > 0 && !showChanges && !alignmentMode && (
               <>
                 <div className="h-4 w-[1px] bg-border" />
                 <Button 
                   variant="default" 
                   size="sm" 
                   className="h-7 gap-1.5 bg-primary"
                   onClick={() => setShowChanges(true)}
                 >
                   <Sparkles className="w-3 h-3" /> Show {changes.length} Changes
                 </Button>
               </>
             )}

             {showChanges && (
               <>
                 <div className="h-4 w-[1px] bg-border" />
                 <Button 
                   variant={isAddingChange ? "default" : "outline"} 
                   size="sm" 
                   className="h-7 gap-1.5"
                   onClick={() => {
                     setIsAddingChange(!isAddingChange);
                     if (!isAddingChange) {
                       setTimeout(() => setShowAddDialog(true), 500);
                     }
                   }}
                 >
                   {isAddingChange ? <X className="w-3 h-3" /> : <Plus className="w-3 h-3" />}
                   {isAddingChange ? "Cancel" : "Add Change"}
                 </Button>
               </>
             )}
          </div>
          
          <div className="flex items-center gap-2">
            <Tabs value={viewMode} onValueChange={(v) => setViewMode(v as "overlay" | "sidebyside")} className="w-[200px]">
              <TabsList className="grid w-full grid-cols-2 h-8">
                <TabsTrigger value="overlay" className="text-xs">Overlay</TabsTrigger>
                <TabsTrigger value="sidebyside" className="text-xs">Side-by-Side</TabsTrigger>
              </TabsList>
            </Tabs>
            <div className="h-4 w-[1px] bg-border mx-2" />
            <Button variant="outline" size="sm" className="h-8 gap-2">
              <Download className="w-3 h-3" /> Export
            </Button>
            <Button size="sm" className="h-8 gap-2">
              <Share2 className="w-3 h-3" /> Share
            </Button>
          </div>
        </div>

        {/* Error Message for Failed Comparisons */}
        {isFailed && (
          <div className="p-4 border-b border-border bg-destructive/10">
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertTitle>Comparison Failed</AlertTitle>
              <AlertDescription>
                The comparison processing failed. This may be due to missing blocks, processing errors, or connectivity issues. 
                Please try creating a new comparison or contact support if the issue persists.
              </AlertDescription>
            </Alert>
          </div>
        )}

        {/* Loading State */}
        {comparisonLoading && !comparison && (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center space-y-4">
              <Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" />
              <p className="text-sm text-muted-foreground">Loading comparison...</p>
            </div>
          </div>
        )}

        {/* Processing State - When comparison is being generated */}
        {!comparisonLoading && comparison && isProcessing && (
          <div className="flex-1 flex items-center justify-center bg-muted/10">
            <div className="text-center space-y-6 max-w-md p-8">
              <div className="relative">
                <div className="w-20 h-20 mx-auto rounded-full bg-primary/10 flex items-center justify-center">
                  <Loader2 className="w-10 h-10 animate-spin text-primary" />
                </div>
                <div className="absolute inset-0 w-20 h-20 mx-auto rounded-full border-4 border-primary/20 animate-ping" style={{ animationDuration: '2s' }} />
              </div>
              <div className="space-y-2">
                <h3 className="text-xl font-semibold">Processing Comparison</h3>
                <p className="text-sm text-muted-foreground">
                  Analyzing drawings and generating overlay...
                </p>
                <p className="text-xs text-muted-foreground">
                  This typically takes 30-60 seconds depending on drawing complexity.
                </p>
              </div>
              <div className="flex items-center justify-center gap-2 text-xs text-muted-foreground">
                <div className="w-2 h-2 bg-primary rounded-full animate-pulse" />
                <span>Comparison ID: {comparison.id.slice(0, 12)}...</span>
              </div>
            </div>
          </div>
        )}

        {/* Main Content Split - Only show when comparison is completed or failed */}
        {!comparisonLoading && comparison && !isProcessing && (
        <ResizablePanelGroup direction="horizontal" className="flex-1">
          {/* Drawing Viewer Panel */}
          <ResizablePanel defaultSize={showChanges ? 75 : 100} minSize={50}>
            {viewMode === "overlay" ? (
              <div className="w-full h-full bg-muted/20 relative overflow-hidden flex flex-col" onClick={handleAlignmentClick}>
                {/* Legend */}
                <div className="absolute top-4 left-4 z-20 bg-white/95 backdrop-blur-sm border border-border rounded-lg p-3 shadow-lg">
                  <p className="text-xs font-semibold mb-2 text-muted-foreground">OVERLAY LEGEND</p>
                  <div className="space-y-1.5">
                    <div className="flex items-center gap-2 text-xs">
                      <div className="w-4 h-4 rounded bg-red-500/30 border-2 border-red-500"></div>
                      <span>Removed (Old)</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <div className="w-4 h-4 rounded bg-green-500/30 border-2 border-green-500"></div>
                      <span>Added (New)</span>
                    </div>
                    <div className="flex items-center gap-2 text-xs">
                      <div className="w-4 h-4 rounded bg-slate-300/50 border-2 border-slate-400"></div>
                      <span>Unchanged</span>
                    </div>
                  </div>
                </div>

                {alignmentMode && (
                  <div className="absolute top-4 right-4 z-20 bg-amber-50 border border-amber-200 rounded-lg p-3 shadow-lg max-w-xs">
                    <p className="text-xs font-medium text-amber-800 mb-2">Manual Alignment Mode</p>
                    <p className="text-xs text-amber-700">
                      Click 3 matching points on each drawing (6 total). Points should be identifiable features like column intersections or corners.
                    </p>
                    <div className="mt-2 flex gap-1">
                      {[1,2,3].map(i => (
                        <div key={i} className={`w-6 h-6 rounded-full border-2 flex items-center justify-center text-xs font-bold ${
                          alignmentPoints >= i ? 'bg-red-500 border-red-500 text-white' : 'border-red-300 text-red-300'
                        }`}>
                          {i}
                        </div>
                      ))}
                      <span className="text-xs text-amber-600 mx-1">→</span>
                      {[4,5,6].map(i => (
                        <div key={i} className={`w-6 h-6 rounded-full border-2 flex items-center justify-center text-xs font-bold ${
                          alignmentPoints >= i ? 'bg-green-500 border-green-500 text-white' : 'border-green-300 text-green-300'
                        }`}>
                          {i - 3}
                        </div>
                      ))}
                    </div>
                  </div>
                )}
                
                {isAddingChange && (
                  <div className="absolute top-4 right-4 z-20 bg-amber-50 border border-amber-200 rounded-lg p-3 shadow-lg">
                    <p className="text-xs font-medium text-amber-800">Click and drag on the drawing to select a region</p>
                  </div>
                )}

                <div className={`flex-1 flex items-center justify-center p-8 ${alignmentMode ? 'cursor-crosshair' : ''}`}>
                  <div className={`relative shadow-2xl max-w-full max-h-full aspect-[4/3] bg-white ${isAddingChange ? 'cursor-crosshair' : ''}`}>
                    <img 
                      src={overlayImage} 
                      alt="Overlay Comparison" 
                      className="w-full h-full object-contain opacity-60"
                    />
                    
                    {/* Change Markers - only show when changes detected */}
                    {showChanges && changes.map((change, i) => {
                      const colors = getChangeColor(change.type);
                      return (
                        <div 
                          key={change.id}
                          onClick={(e) => { e.stopPropagation(); handleSelectChange(change.id); }}
                          className={`
                            absolute w-12 h-12 border-2 rounded-full flex items-center justify-center cursor-pointer hover:scale-110 transition-transform z-10 shadow-lg
                            ${activeChangeId === change.id ? 'ring-4 ring-primary/20 scale-110' : ''}
                            ${colors.border} ${colors.bg} ${colors.text}
                          `}
                          style={{ 
                            top: `${20 + (i * 12)}%`, 
                            left: `${25 + (i * 12)}%` 
                          }}
                        >
                          <span className="font-bold text-xs">{i + 1}</span>
                        </div>
                      );
                    })}

                    {/* Alignment point indicators */}
                    {alignmentMode && alignmentPoints > 0 && (
                      <>
                        {alignmentPoints >= 1 && <div className="absolute w-4 h-4 bg-red-500 rounded-full border-2 border-white shadow-lg" style={{ top: '30%', left: '20%' }} />}
                        {alignmentPoints >= 2 && <div className="absolute w-4 h-4 bg-red-500 rounded-full border-2 border-white shadow-lg" style={{ top: '30%', left: '80%' }} />}
                        {alignmentPoints >= 3 && <div className="absolute w-4 h-4 bg-red-500 rounded-full border-2 border-white shadow-lg" style={{ top: '80%', left: '50%' }} />}
                        {alignmentPoints >= 4 && <div className="absolute w-4 h-4 bg-green-500 rounded-full border-2 border-white shadow-lg" style={{ top: '32%', left: '22%' }} />}
                        {alignmentPoints >= 5 && <div className="absolute w-4 h-4 bg-green-500 rounded-full border-2 border-white shadow-lg" style={{ top: '32%', left: '78%' }} />}
                        {alignmentPoints >= 6 && <div className="absolute w-4 h-4 bg-green-500 rounded-full border-2 border-white shadow-lg" style={{ top: '78%', left: '52%' }} />}
                      </>
                    )}
                  </div>
                </div>

                {!showChanges && !alignmentMode && isCompleted && (
                  <div className="absolute bottom-8 left-1/2 -translate-x-1/2 bg-background/95 backdrop-blur-sm border border-border rounded-lg px-6 py-4 shadow-lg text-center">
                    <p className="text-sm text-muted-foreground mb-2">Overlay generated successfully.</p>
                    <p className="text-xs text-muted-foreground">
                      {changes.length > 0 
                        ? `${changes.length} changes detected. Use "Manual Align" to adjust alignment if needed.`
                        : 'No changes detected. Use "Manual Align" to adjust alignment if needed.'}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              /* Side-by-Side View */
              <div className="w-full h-full flex">
                <div className="flex-1 border-r border-border bg-muted/10 relative flex flex-col">
                  <div className="h-8 bg-muted/30 border-b border-border flex items-center justify-center">
                    <span className="text-xs font-medium text-muted-foreground">Previous Revision (Rev 0)</span>
                  </div>
                  <div className="flex-1 flex items-center justify-center p-4 overflow-hidden">
                    <div className="relative max-w-full max-h-full bg-white shadow-lg">
                      <img src={blueprint} alt="Old Drawing" className="w-full h-full object-contain opacity-70" />
                      {showChanges && changes.filter(c => c.type === 'deleted').map((change, i) => (
                        <div 
                          key={change.id}
                          onClick={() => handleSelectChange(change.id)}
                          className="absolute w-10 h-10 border-2 border-red-500 bg-red-500/20 rounded-full flex items-center justify-center cursor-pointer hover:scale-110 transition-transform"
                          style={{ top: `${25 + (i * 20)}%`, left: `${30 + (i * 15)}%` }}
                        >
                          <span className="font-bold text-xs text-red-600">{changes.indexOf(change) + 1}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
                <div className="flex-1 bg-muted/10 relative flex flex-col">
                  <div className="h-8 bg-muted/30 border-b border-border flex items-center justify-center">
                    <span className="text-xs font-medium text-muted-foreground">Current Revision (Rev 1)</span>
                  </div>
                  <div className="flex-1 flex items-center justify-center p-4 overflow-hidden">
                    <div className="relative max-w-full max-h-full bg-white shadow-lg">
                      <img src={blueprint} alt="New Drawing" className="w-full h-full object-contain" />
                      {showChanges && changes.filter(c => c.type === 'new').map((change, i) => (
                        <div 
                          key={change.id}
                          onClick={() => handleSelectChange(change.id)}
                          className="absolute w-10 h-10 border-2 border-green-500 bg-green-500/20 rounded-full flex items-center justify-center cursor-pointer hover:scale-110 transition-transform"
                          style={{ top: `${30 + (i * 18)}%`, left: `${35 + (i * 12)}%` }}
                        >
                          <span className="font-bold text-xs text-green-600">{changes.indexOf(change) + 1}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </ResizablePanel>

          {showChanges && (
            <>
              <ResizableHandle />

              {/* Change List Panel */}
              <ResizablePanel defaultSize={25} minSize={20} maxSize={40} className="bg-background border-l border-border flex flex-col">
                <div className="p-4 border-b border-border flex items-center justify-between">
                  <h3 className="font-semibold text-sm">Detected Changes</h3>
                  <Button variant="ghost" size="icon" className="h-8 w-8"><Filter className="w-4 h-4" /></Button>
                </div>
                
                <ScrollArea className="flex-1">
                  <div className="p-4 space-y-3">
                    {/* AI Analysis Loading State */}
                    {isAnalyzing && (
                      <div className="p-6 rounded-xl border-2 border-dashed border-primary/30 bg-primary/5 animate-pulse">
                        <div className="flex flex-col items-center text-center space-y-4">
                          <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                            <Bot className="w-6 h-6 text-primary animate-pulse" />
                          </div>
                          <div>
                            <h4 className="font-semibold text-sm mb-1">AI Analyzing Changes</h4>
                            <p className="text-xs text-muted-foreground">
                              Detecting modifications, estimating costs...
                            </p>
                          </div>
                          <Progress value={66} className="w-full h-2" />
                          <div className="flex items-center gap-2 text-xs text-muted-foreground">
                            <Loader2 className="w-3 h-3 animate-spin" />
                            <span>This may take 30-60 seconds</span>
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {/* No changes yet - prompt to run AI Analysis */}
                    {!isAnalyzing && changes.length === 0 && (
                      <div className="p-6 rounded-xl border-2 border-dashed border-border bg-muted/20">
                        <div className="flex flex-col items-center text-center space-y-3">
                          <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center">
                            <Sparkles className="w-6 h-6 text-muted-foreground" />
                          </div>
                          <div>
                            <h4 className="font-semibold text-sm mb-1">No Changes Detected Yet</h4>
                            <p className="text-xs text-muted-foreground">
                              Click "AI Analysis" below to automatically detect changes with cost & schedule estimates.
                            </p>
                          </div>
                        </div>
                      </div>
                    )}
                    
                    {/* Changes List */}
                    {changes.map((change, i) => {
                      const colors = getChangeColor(change.type);
                      return (
                        <div 
                          key={change.id}
                          onClick={() => handleSelectChange(change.id)}
                          className={`
                            p-3 rounded-lg border cursor-pointer transition-all hover:shadow-md
                            ${activeChangeId === change.id ? 'border-primary bg-primary/5 ring-1 ring-primary/20' : 'border-border bg-card hover:border-primary/50'}
                          `}
                        >
                          <div className="flex justify-between items-start mb-2">
                             <Badge className={`capitalize text-[10px] h-5 px-1.5 ${change.type === 'new' ? 'bg-green-500 hover:bg-green-600' : 'bg-red-500 hover:bg-red-600'}`}>
                                {change.type === 'new' ? 'Added' : 'Removed'}
                             </Badge>
                             <span className="text-xs font-mono text-muted-foreground">#{i + 1}</span>
                          </div>
                          <h4 className="font-medium text-sm mb-2">{change.title}</h4>
                          
                          <div className="grid grid-cols-2 gap-2 text-xs mb-3">
                            <div className="flex items-center gap-1.5 text-muted-foreground">
                              <DollarSign className="w-3 h-3" />
                              <span>{change.cost}</span>
                            </div>
                            <div className="flex items-center gap-1.5 text-muted-foreground">
                              <CalendarDays className="w-3 h-3" />
                              <span>{change.schedule}</span>
                            </div>
                            <div className="flex items-center gap-1.5 text-muted-foreground">
                              <Layers className="w-3 h-3" />
                              <span>{change.discipline}</span>
                            </div>
                            <div className="flex items-center gap-1.5 text-muted-foreground text-[10px]">
                              Sheet: {change.sheet}
                            </div>
                          </div>

                          <div className="flex items-center justify-between pt-2 border-t border-border/50">
                             <div className="flex items-center gap-1.5">
                               <Avatar className="w-4 h-4">
                                 <AvatarFallback className="text-[8px]">{change.assignee === "Unassigned" ? "?" : change.assignee.charAt(0)}</AvatarFallback>
                               </Avatar>
                               <span className="text-[10px] text-muted-foreground truncate max-w-[80px]">{change.assignee}</span>
                             </div>
                             <Badge variant="outline" className={`text-[10px] h-4 ${
                               change.status === 'Open' ? 'border-blue-200 text-blue-600 bg-blue-50' :
                               change.status === 'In Review' ? 'border-amber-200 text-amber-600 bg-amber-50' :
                               change.status === 'Pricing' ? 'border-purple-200 text-purple-600 bg-purple-50' :
                               'border-green-200 text-green-600 bg-green-50'
                             }`}>{change.status}</Badge>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </ScrollArea>

                <div className="p-4 border-t border-border bg-muted/10 space-y-2">
                   <Button className="w-full gap-2" onClick={() => window.location.href = '/project/1/cost'}>
                     <BarChart3 className="w-4 h-4" /> Analyze Cost & Schedule Impact
                   </Button>
                   <Button 
                     variant="outline" 
                     className="w-full gap-2"
                     onClick={runAIAnalysis}
                     disabled={isAnalyzing || !comparison?.id}
                   >
                     {isAnalyzing ? (
                       <>
                         <Loader2 className="w-4 h-4 animate-spin" /> Analyzing...
                       </>
                     ) : (
                       <>
                         <Bot className="w-4 h-4" /> AI Analysis
                       </>
                     )}
                   </Button>
                </div>
              </ResizablePanel>
            </>
          )}
        </ResizablePanelGroup>
        )}

        {/* Floating Chat Button */}
        <Button
          onClick={() => setChatOpen(!chatOpen)}
          className="fixed bottom-6 right-6 w-14 h-14 rounded-full shadow-2xl z-50"
          size="icon"
        >
          {chatOpen ? <X className="w-6 h-6" /> : <MessageCircle className="w-6 h-6" />}
        </Button>

        {/* Chat Panel */}
        {chatOpen && (
          <div className="fixed bottom-24 right-6 w-96 h-[500px] bg-background border border-border rounded-xl shadow-2xl z-50 flex flex-col overflow-hidden">
            <div className="p-4 border-b border-border bg-primary/5 flex items-center gap-3">
              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                <Bot className="w-5 h-5 text-primary" />
              </div>
              <div>
                <p className="font-semibold text-sm">BuildTrace AI</p>
                <p className="text-xs text-muted-foreground">Drawing analysis assistant</p>
              </div>
            </div>
            
            <ScrollArea className="flex-1 p-4">
              <div className="space-y-4">
                {chatMessages.map((msg, i) => (
                  <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[80%] p-3 rounded-lg text-sm ${
                      msg.role === 'user' 
                        ? 'bg-primary text-primary-foreground rounded-br-sm' 
                        : 'bg-muted rounded-bl-sm'
                    }`}>
                      {msg.content}
                    </div>
                  </div>
                ))}
              </div>
            </ScrollArea>

            <div className="p-4 border-t border-border">
              <div className="flex gap-2">
                <Input 
                  placeholder="Ask about drawings or changes..." 
                  value={chatInput}
                  onChange={(e) => setChatInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
                  className="flex-1"
                />
                <Button size="icon" onClick={handleSendMessage}>
                  <Send className="w-4 h-4" />
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Details Sheet */}
        <Sheet open={isSheetOpen} onOpenChange={setIsSheetOpen}>
          <SheetContent className="w-[400px] sm:w-[540px] overflow-y-auto">
            {activeChange ? (
              <div className="space-y-6">
                <SheetHeader>
                  <div className="flex items-center gap-2 mb-2">
                    <Badge variant="outline">#{activeChange.id}</Badge>
                    <Badge className={activeChange.type === 'new' ? 'bg-green-500' : 'bg-red-500'}>
                      {activeChange.type === 'new' ? 'Added' : 'Removed'}
                    </Badge>
                  </div>
                  <SheetTitle className="text-xl">{activeChange.title}</SheetTitle>
                  <SheetDescription>
                    Sheet {activeChange.sheet} • {activeChange.discipline} • Coordinates E5-F5
                  </SheetDescription>
                </SheetHeader>
                
                <div className="space-y-4">
                  <div className="space-y-2">
                    <Label>Description</Label>
                    <Textarea defaultValue={activeChange.title} className="min-h-[80px]" />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="p-4 rounded-lg bg-muted/30 border border-border">
                    <p className="text-xs text-muted-foreground mb-1">Estimated Cost</p>
                    <Input defaultValue={activeChange.cost} className="h-8 text-lg font-bold" />
                  </div>
                  <div className="p-4 rounded-lg bg-muted/30 border border-border">
                     <p className="text-xs text-muted-foreground mb-1">Schedule Impact</p>
                     <Input defaultValue={activeChange.schedule} className="h-8 text-lg font-bold" />
                  </div>
                </div>

                <div className="space-y-4">
                  <h3 className="font-medium text-sm">Status & Assignment</h3>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                       <Label className="text-xs">Status</Label>
                       <Select defaultValue={activeChange.status.toLowerCase().replace(" ", "-")}>
                         <SelectTrigger>
                           <SelectValue placeholder="Status" />
                         </SelectTrigger>
                         <SelectContent>
                           <SelectItem value="open">Open</SelectItem>
                           <SelectItem value="in-review">In Review</SelectItem>
                           <SelectItem value="pricing">Pricing</SelectItem>
                           <SelectItem value="closed">Closed</SelectItem>
                         </SelectContent>
                       </Select>
                    </div>
                    <div className="space-y-2">
                       <Label className="text-xs">Assignee</Label>
                       <Select defaultValue={activeChange.assignee === "Unassigned" ? "unassigned" : "alex"}>
                         <SelectTrigger>
                           <SelectValue placeholder="Assignee" />
                         </SelectTrigger>
                         <SelectContent>
                           <SelectItem value="unassigned">Unassigned</SelectItem>
                           <SelectItem value="alex">Alex Morgan</SelectItem>
                           <SelectItem value="sarah">Sarah Chen</SelectItem>
                           <SelectItem value="mike">Mike Ross</SelectItem>
                         </SelectContent>
                       </Select>
                    </div>
                  </div>
                </div>

                <Separator />

                <div className="space-y-4">
                  <h3 className="font-medium text-sm flex items-center gap-2">
                    <MessageSquare className="w-4 h-4" /> Discussion
                  </h3>
                  
                  <div className="space-y-4 max-h-[200px] overflow-y-auto pr-2">
                    <div className="flex gap-3">
                       <Avatar className="w-8 h-8">
                         <AvatarFallback>SM</AvatarFallback>
                       </Avatar>
                       <div className="flex-1 space-y-1">
                         <div className="flex items-center gap-2">
                           <span className="text-sm font-medium">Sarah Miller</span>
                           <span className="text-xs text-muted-foreground">2 hours ago</span>
                         </div>
                         <p className="text-sm text-muted-foreground bg-muted p-3 rounded-md rounded-tl-none">
                           Is this change captured in RFI #104?
                         </p>
                       </div>
                    </div>
                  </div>

                  <div className="flex gap-2">
                    <Input placeholder="Reply..." className="flex-1" />
                    <Button size="icon"><Send className="w-4 h-4" /></Button>
                  </div>
                </div>

                <SheetFooter className="pt-4 border-t border-border">
                  <Button className="w-full">
                    <Save className="w-4 h-4 mr-2" /> Save Changes
                  </Button>
                </SheetFooter>
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-muted-foreground">
                Select a change to view details
              </div>
            )}
          </SheetContent>
        </Sheet>

        {/* Add Change Dialog */}
        <Dialog open={showAddDialog} onOpenChange={setShowAddDialog}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Change</DialogTitle>
              <DialogDescription>
                Define the change you want to track on this drawing.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Sheet ID</Label>
                  <Input defaultValue="A-101" disabled />
                </div>
                <div className="space-y-2">
                  <Label>Coordinates</Label>
                  <Input defaultValue="G4-H5" disabled />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Description</Label>
                <Textarea placeholder="Describe the change..." />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Cost Impact</Label>
                  <Input placeholder="$0" />
                </div>
                <div className="space-y-2">
                  <Label>Schedule Impact</Label>
                  <Input placeholder="0 Days" />
                </div>
              </div>
              <div className="space-y-2">
                <Label>Status</Label>
                <Select defaultValue="open">
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="open">Open</SelectItem>
                    <SelectItem value="in-review">In Review</SelectItem>
                    <SelectItem value="pricing">Pricing</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => { setShowAddDialog(false); setIsAddingChange(false); }}>Cancel</Button>
              <Button onClick={() => { setShowAddDialog(false); setIsAddingChange(false); }}>Create Change</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        </>
        )}
      </div>
    </DashboardLayout>
  );
}
