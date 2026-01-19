import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from "@/components/ui/resizable";
import { Link, useLocation } from "wouter";
import {
  Upload,
  ArrowRight,
  FileText,
  CheckCircle2,
  Loader2,
  Download,
  ArrowLeft,
  X,
  Image as ImageIcon,
  Save,
  LogIn,
  Bot,
  DollarSign,
  CalendarDays,
  Layers,
  Sparkles
} from "lucide-react";
import { useToast } from "@/hooks/use-toast";
import logo from "@assets/BuildTrace_Logo_1767832159404.jpg";

// Public comparison page - no authentication required
export default function TryCompare() {
  const [, setLocation] = useLocation();
  const { toast } = useToast();

  // Step state: upload -> processing -> results -> save
  const [step, setStep] = useState<"upload" | "processing" | "results" | "save">("upload");

  // File state
  const [oldFile, setOldFile] = useState<File | null>(null);
  const [newFile, setNewFile] = useState<File | null>(null);
  const [oldPreview, setOldPreview] = useState<string | null>(null);
  const [newPreview, setNewPreview] = useState<string | null>(null);

  // Processing state
  const [uploadProgress, setUploadProgress] = useState(0);
  const [processingStatus, setProcessingStatus] = useState<string>("");
  const [comparisonId, setComparisonId] = useState<string | null>(null);

  // Results state
  const [overlayUri, setOverlayUri] = useState<string | null>(null);
  const [comparisonScore, setComparisonScore] = useState<number | null>(null);
  
  // AI Analysis state
  const [isAnalyzing, setIsAnalyzing] = useState(false);
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
  const [showChanges, setShowChanges] = useState(false);

  // File input refs
  const oldFileInputRef = useRef<HTMLInputElement>(null);
  const newFileInputRef = useRef<HTMLInputElement>(null);

  // Handle file selection
  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>, type: "old" | "new") => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (type === "old") {
      setOldFile(file);
      // Create preview for PDF (first page) or image
      if (file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = (e) => setOldPreview(e.target?.result as string);
        reader.readAsDataURL(file);
      } else {
        setOldPreview(null);
      }
    } else {
      setNewFile(file);
      if (file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = (e) => setNewPreview(e.target?.result as string);
        reader.readAsDataURL(file);
      } else {
        setNewPreview(null);
      }
    }
  };

  // Start comparison process
  const startComparison = async () => {
    if (!oldFile || !newFile) {
      toast({
        title: "Missing files",
        description: "Please upload both drawings to compare.",
        variant: "destructive",
      });
      return;
    }

    setStep("processing");
    setProcessingStatus("Uploading files...");
    setUploadProgress(10);

    try {
      // Ensure API_BASE includes /api prefix (same logic as api.ts)
      const BASE_URL = import.meta.env.VITE_API_URL || '';
      const API_BASE = BASE_URL.endsWith('/api') ? BASE_URL : BASE_URL ? `${BASE_URL}/api` : '/api';

      // Upload old file
      setProcessingStatus("Uploading OLD drawing...");
      const oldFormData = new FormData();
      oldFormData.append("file", oldFile);

      const oldUploadResponse = await fetch(`${API_BASE}/uploads/public/upload`, {
        method: "POST",
        body: oldFormData,
      });

      if (!oldUploadResponse.ok) {
        throw new Error("Failed to upload old drawing");
      }

      const oldUploadData = await oldUploadResponse.json();
      setUploadProgress(30);

      // Upload new file
      setProcessingStatus("Uploading NEW drawing...");
      const newFormData = new FormData();
      newFormData.append("file", newFile);

      const newUploadResponse = await fetch(`${API_BASE}/uploads/public/upload`, {
        method: "POST",
        body: newFormData,
      });

      if (!newUploadResponse.ok) {
        throw new Error("Failed to upload new drawing");
      }

      const newUploadData = await newUploadResponse.json();
      setUploadProgress(50);

      // Create public comparison
      setProcessingStatus("Starting comparison...");
      const compareResponse = await fetch(`${API_BASE}/comparisons/public/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          old_uri: oldUploadData.uri,
          new_uri: newUploadData.uri,
        }),
      });

      if (!compareResponse.ok) {
        throw new Error("Failed to start comparison");
      }

      const compareData = await compareResponse.json();
      setComparisonId(compareData.id);
      setUploadProgress(70);

      // Poll for completion
      setProcessingStatus("Processing drawings...");
      pollComparison(compareData.id);
    } catch (error) {
      console.error("Comparison error:", error);
      toast({
        title: "Comparison failed",
        description: error instanceof Error ? error.message : "An error occurred",
        variant: "destructive",
      });
      setStep("upload");
    }
  };

  // Poll for comparison completion
  const pollComparison = async (id: string) => {
    // Ensure API_BASE includes /api prefix (same logic as api.ts)
    const BASE_URL = import.meta.env.VITE_API_URL || '';
    const API_BASE = BASE_URL.endsWith('/api') ? BASE_URL : BASE_URL ? `${BASE_URL}/api` : '/api';
    let attempts = 0;
    const maxAttempts = 300; // 5 minutes max (for complex PDFs with grid alignment)

    const poll = async () => {
      try {
        const response = await fetch(`${API_BASE}/comparisons/${id}`);
        if (!response.ok) throw new Error("Failed to fetch comparison");

        const data = await response.json();

        if (data.status === "completed") {
          setUploadProgress(100);
          setOverlayUri(data.overlay_uri);
          setComparisonScore(data.score);
          setStep("results");
          toast({
            title: "Comparison complete!",
            description: "Your drawings have been compared.",
          });
        } else if (data.status === "failed") {
          throw new Error("Comparison processing failed");
        } else if (attempts < maxAttempts) {
          attempts++;
          setUploadProgress(70 + Math.min(attempts * 0.77, 28)); // Scale progress over 5 minutes
          const minutes = Math.floor(attempts / 60);
          const seconds = attempts % 60;
          setProcessingStatus(`Processing... (${minutes}m ${seconds}s)`);
          setTimeout(poll, 1000);
        } else {
          // Timeout reached, but check one more time in case it just completed
          const finalCheck = await fetch(`${API_BASE}/comparisons/${id}`);
          if (finalCheck.ok) {
            const finalData = await finalCheck.json();
            if (finalData.status === "completed") {
              setUploadProgress(100);
              setOverlayUri(finalData.overlay_uri);
              setComparisonScore(finalData.score);
              setStep("results");
              toast({
                title: "Comparison complete!",
                description: "Your drawings have been compared.",
              });
              return;
            }
          }
          throw new Error("Comparison is taking longer than expected. The comparison may still be processing. Please refresh the page in a few minutes.");
        }
      } catch (error) {
        console.error("Poll error:", error);
        toast({
          title: "Processing failed",
          description: error instanceof Error ? error.message : "An error occurred",
          variant: "destructive",
        });
        setStep("upload");
      }
    };

    poll();
  };

  // Export comparison as CSV
  const handleExportCSV = () => {
    const csvContent = `Comparison Report
Date,${new Date().toLocaleDateString()}
Score,${comparisonScore || "N/A"}
Old Drawing,${oldFile?.name || "Unknown"}
New Drawing,${newFile?.name || "Unknown"}

Changes detected in overlay comparison.
View the overlay image for visual differences.
`;

    const blob = new Blob([csvContent], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `comparison-${comparisonId || "export"}.csv`;
    link.click();
    URL.revokeObjectURL(url);

    toast({
      title: "Export successful",
      description: "Comparison report downloaded.",
    });
  };

  // Download overlay image
  const handleDownloadOverlay = () => {
    if (overlayUri) {
      window.open(overlayUri, "_blank");
    }
  };

  // Navigate to save/signup
  const handleSaveToAccount = () => {
    setStep("save");
  };

  // Clear all and start over
  const handleStartOver = () => {
    setOldFile(null);
    setNewFile(null);
    setOldPreview(null);
    setNewPreview(null);
    setUploadProgress(0);
    setProcessingStatus("");
    setComparisonId(null);
    setOverlayUri(null);
    setComparisonScore(null);
    setAiDetectedChanges([]);
    setAnalysisSummary(null);
    setShowChanges(false);
    setIsAnalyzing(false);
    setStep("upload");
  };

  // Run AI Analysis
  const runAIAnalysis = async () => {
    if (!comparisonId) {
      toast({
        title: "No comparison available",
        description: "Please wait for the comparison to complete first.",
        variant: "destructive",
      });
      return;
    }
    
    setIsAnalyzing(true);
    setShowChanges(true);
    
    try {
      const BASE_URL = import.meta.env.VITE_API_URL || '';
      const API_BASE = BASE_URL.endsWith('/api') ? BASE_URL : BASE_URL ? `${BASE_URL}/api` : '/api';
      
      // Call the AI change detection API (endpoint format: /analysis/detect-changes/{overlay_id}?use_ai=true)
      const detectResponse = await fetch(`${API_BASE}/analysis/detect-changes/${comparisonId}?use_ai=true`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });
      
      if (!detectResponse.ok) {
        throw new Error("Failed to start AI analysis");
      }
      
      const detectResult = await detectResponse.json();
      
      toast({
        title: "AI Analysis Started",
        description: detectResult.message || "Analyzing changes with AI...",
      });
      
      // Poll for results
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
          const summaryResponse = await fetch(`${API_BASE}/analysis/summary/${comparisonId}`);
          if (summaryResponse.ok) {
            const summary = await summaryResponse.json();
            if (summary.changes && summary.changes.length > 0) {
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
      toast({
        title: "Analysis Failed",
        description: errorMsg,
        variant: "destructive",
      });
    }
  };

  // Load existing analysis results when comparison completes
  useEffect(() => {
    const loadExistingAnalysis = async () => {
      if (!comparisonId || step !== "results") return;
      try {
        const BASE_URL = import.meta.env.VITE_API_URL || '';
        const API_BASE = BASE_URL.endsWith('/api') ? BASE_URL : BASE_URL ? `${BASE_URL}/api` : '/api';
        const summaryResponse = await fetch(`${API_BASE}/analysis/summary/${comparisonId}`);
        if (summaryResponse.ok) {
          const summary = await summaryResponse.json();
          if (summary.changes && summary.changes.length > 0) {
            setAiDetectedChanges(summary.changes);
            setAnalysisSummary(summary.summary || null);
            setShowChanges(true);
          }
        }
      } catch {
        // No existing analysis, that's fine
      }
    };
    loadExistingAnalysis();
  }, [comparisonId, step]);

  const getChangeColor = (type: string) => {
    switch(type) {
      case 'new': return { border: 'border-green-500', bg: 'bg-green-500/20', text: 'text-green-600' };
      case 'deleted': return { border: 'border-red-500', bg: 'bg-red-500/20', text: 'text-red-600' };
      default: return { border: 'border-slate-400', bg: 'bg-slate-400/20', text: 'text-slate-500' };
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Link href="/">
            <div className="flex items-center gap-2 cursor-pointer">
              <img src={logo} alt="BuildTrace" className="w-8 h-8 rounded-md" />
              <span className="text-xl font-bold font-display">BuildTrace</span>
            </div>
          </Link>
          <div className="flex items-center gap-4">
            <Link href="/auth">
              <Button variant="outline">
                <LogIn className="w-4 h-4 mr-2" />
                Sign In
              </Button>
            </Link>
          </div>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 max-w-4xl">
        {/* Upload Step */}
        {step === "upload" && (
          <div className="space-y-8">
            <div className="text-center space-y-2">
              <h1 className="text-3xl font-bold font-display">Compare Drawings</h1>
              <p className="text-muted-foreground max-w-lg mx-auto">
                Upload two drawings to compare and see the differences. No account required.
              </p>
            </div>

            <div className="grid md:grid-cols-2 gap-6">
              {/* Old Drawing */}
              <Card className="border-2 border-dashed hover:border-red-300 transition-colors">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-red-100 text-red-600 flex items-center justify-center text-xs font-bold">1</div>
                      OLD Drawing
                    </CardTitle>
                    <Badge variant="outline" className="text-red-600 border-red-200">Previous</Badge>
                  </div>
                  <CardDescription>Upload the original/older version</CardDescription>
                </CardHeader>
                <CardContent>
                  <input
                    ref={oldFileInputRef}
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg,.dwg,.dxf"
                    className="hidden"
                    onChange={(e) => handleFileSelect(e, "old")}
                  />

                  {!oldFile ? (
                    <div
                      className="border-2 border-dashed border-border rounded-xl p-8 text-center hover:border-red-300 transition-all cursor-pointer"
                      onClick={() => oldFileInputRef.current?.click()}
                    >
                      <Upload className="w-10 h-10 mx-auto mb-3 text-muted-foreground" />
                      <p className="font-medium">Drop file or click to upload</p>
                      <p className="text-sm text-muted-foreground mt-1">PDF, PNG, JPG, DWG, DXF</p>
                    </div>
                  ) : (
                    <div className="p-4 rounded-lg bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <CheckCircle2 className="w-5 h-5 text-red-600" />
                          <div>
                            <p className="font-medium text-sm truncate max-w-[200px]">{oldFile.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {(oldFile.size / 1024 / 1024).toFixed(2)} MB
                            </p>
                          </div>
                        </div>
                        <Button variant="ghost" size="icon" onClick={() => { setOldFile(null); setOldPreview(null); }}>
                          <X className="w-4 h-4" />
                        </Button>
                      </div>
                      {oldPreview && (
                        <div className="mt-3 rounded overflow-hidden">
                          <img src={oldPreview} alt="Old drawing preview" className="w-full h-32 object-cover" />
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* New Drawing */}
              <Card className="border-2 border-dashed hover:border-green-300 transition-colors">
                <CardHeader className="pb-3">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg flex items-center gap-2">
                      <div className="w-6 h-6 rounded-full bg-green-100 text-green-600 flex items-center justify-center text-xs font-bold">2</div>
                      NEW Drawing
                    </CardTitle>
                    <Badge variant="outline" className="text-green-600 border-green-200">Current</Badge>
                  </div>
                  <CardDescription>Upload the newer version to compare</CardDescription>
                </CardHeader>
                <CardContent>
                  <input
                    ref={newFileInputRef}
                    type="file"
                    accept=".pdf,.png,.jpg,.jpeg,.dwg,.dxf"
                    className="hidden"
                    onChange={(e) => handleFileSelect(e, "new")}
                  />

                  {!newFile ? (
                    <div
                      className="border-2 border-dashed border-border rounded-xl p-8 text-center hover:border-green-300 transition-all cursor-pointer"
                      onClick={() => newFileInputRef.current?.click()}
                    >
                      <Upload className="w-10 h-10 mx-auto mb-3 text-muted-foreground" />
                      <p className="font-medium">Drop file or click to upload</p>
                      <p className="text-sm text-muted-foreground mt-1">PDF, PNG, JPG, DWG, DXF</p>
                    </div>
                  ) : (
                    <div className="p-4 rounded-lg bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <CheckCircle2 className="w-5 h-5 text-green-600" />
                          <div>
                            <p className="font-medium text-sm truncate max-w-[200px]">{newFile.name}</p>
                            <p className="text-xs text-muted-foreground">
                              {(newFile.size / 1024 / 1024).toFixed(2)} MB
                            </p>
                          </div>
                        </div>
                        <Button variant="ghost" size="icon" onClick={() => { setNewFile(null); setNewPreview(null); }}>
                          <X className="w-4 h-4" />
                        </Button>
                      </div>
                      {newPreview && (
                        <div className="mt-3 rounded overflow-hidden">
                          <img src={newPreview} alt="New drawing preview" className="w-full h-32 object-cover" />
                        </div>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Compare Button */}
            <div className="flex justify-center">
              <Button
                size="lg"
                onClick={startComparison}
                disabled={!oldFile || !newFile}
                className="px-8"
              >
                Compare Drawings
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </div>
          </div>
        )}

        {/* Processing Step */}
        {step === "processing" && (
          <div className="space-y-8">
            <div className="text-center space-y-4">
              <Loader2 className="w-16 h-16 mx-auto text-primary animate-spin" />
              <h2 className="text-2xl font-bold font-display">Processing Your Comparison</h2>
              <p className="text-muted-foreground">{processingStatus}</p>
            </div>

            <div className="max-w-md mx-auto">
              <Progress value={uploadProgress} className="h-2" />
              <p className="text-sm text-center mt-2 text-muted-foreground">{uploadProgress}% complete</p>
            </div>

            <div className="grid md:grid-cols-2 gap-4 max-w-lg mx-auto">
              <Card className="p-4">
                <div className="flex items-center gap-3">
                  <FileText className="w-8 h-8 text-red-500" />
                  <div>
                    <p className="text-sm font-medium truncate">{oldFile?.name}</p>
                    <p className="text-xs text-muted-foreground">OLD Drawing</p>
                  </div>
                </div>
              </Card>
              <Card className="p-4">
                <div className="flex items-center gap-3">
                  <FileText className="w-8 h-8 text-green-500" />
                  <div>
                    <p className="text-sm font-medium truncate">{newFile?.name}</p>
                    <p className="text-xs text-muted-foreground">NEW Drawing</p>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        )}

        {/* Results Step */}
        {step === "results" && (
          <div className="space-y-6">
            <div className="text-center space-y-2">
              <CheckCircle2 className="w-12 h-12 mx-auto text-green-500" />
              <h2 className="text-2xl font-bold font-display">Comparison Complete!</h2>
              <p className="text-muted-foreground">
                {oldFile?.name} vs {newFile?.name}
              </p>
            </div>

            {/* Overlay with Sidebar */}
            {overlayUri && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-xs">
                      {showChanges ? "Changes View" : "Overlay View"}
                    </Badge>
                    {comparisonScore !== null && (
                      <Badge variant="secondary" className="text-xs">
                        Alignment Score: {(comparisonScore * 100).toFixed(1)}%
                      </Badge>
                    )}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setShowChanges(!showChanges)}
                    className="gap-2"
                  >
                    <Bot className="w-4 h-4" />
                    {showChanges ? "Hide Analysis" : "Show AI Analysis"}
                  </Button>
                </div>
                <ResizablePanelGroup direction="horizontal" className="min-h-[600px]">
                  <ResizablePanel defaultSize={showChanges ? 75 : 100} minSize={50}>
                    <Card className="overflow-hidden h-full flex flex-col">
                      <CardHeader className="pb-2">
                        <CardTitle className="text-lg">Overlay Result</CardTitle>
                        <CardDescription>
                          Red areas show additions, green areas show deletions
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="flex-1 flex items-center justify-center p-4">
                        <div className="rounded-lg overflow-hidden border bg-muted w-full h-full flex items-center justify-center">
                          <img
                            src={overlayUri}
                            alt="Comparison overlay"
                            className="max-w-full max-h-full object-contain"
                          />
                        </div>
                      </CardContent>
                    </Card>
                  </ResizablePanel>

                {showChanges && (
                  <>
                    <ResizableHandle />
                    <ResizablePanel defaultSize={25} minSize={20} maxSize={40} className="bg-background border-l border-border flex flex-col">
                      <div className="p-4 border-b border-border flex items-center justify-between">
                        <div>
                          <h3 className="font-semibold text-sm">Detected Changes</h3>
                          {aiDetectedChanges.length > 0 && (
                            <p className="text-xs text-muted-foreground mt-1">
                              {aiDetectedChanges.length} change{aiDetectedChanges.length !== 1 ? 's' : ''} found
                            </p>
                          )}
                        </div>
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
                          {!isAnalyzing && aiDetectedChanges.length === 0 && (
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
                          {aiDetectedChanges.map((change, i) => {
                            const colors = getChangeColor(change.type);
                            return (
                              <div 
                                key={change.id}
                                className={`
                                  p-3 rounded-lg border cursor-pointer transition-all hover:shadow-md
                                  ${colors.border} ${colors.bg}
                                `}
                              >
                                <div className="flex justify-between items-start mb-2">
                                  <Badge className={`capitalize text-[10px] h-5 px-1.5 ${change.type === 'new' ? 'bg-green-500 hover:bg-green-600' : 'bg-red-500 hover:bg-red-600'}`}>
                                    {change.type === 'new' ? 'Added' : 'Removed'}
                                  </Badge>
                                  <span className="text-xs font-mono text-muted-foreground">#{i + 1}</span>
                                </div>
                                <h4 className="font-medium text-sm mb-2">{change.title}</h4>
                                {change.description && (
                                  <p className="text-xs text-muted-foreground mb-3">{change.description}</p>
                                )}
                                
                                <div className="grid grid-cols-2 gap-2 text-xs">
                                  {change.estimated_cost && (
                                    <div className="flex items-center gap-1.5 text-muted-foreground">
                                      <DollarSign className="w-3 h-3" />
                                      <span>{change.estimated_cost}</span>
                                    </div>
                                  )}
                                  {change.schedule_impact && (
                                    <div className="flex items-center gap-1.5 text-muted-foreground">
                                      <CalendarDays className="w-3 h-3" />
                                      <span>{change.schedule_impact}</span>
                                    </div>
                                  )}
                                  {change.discipline && (
                                    <div className="flex items-center gap-1.5 text-muted-foreground">
                                      <Layers className="w-3 h-3" />
                                      <span>{change.discipline}</span>
                                    </div>
                                  )}
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </ScrollArea>

                      <div className="p-4 border-t border-border bg-muted/10 space-y-2">
                        <Button 
                          variant="outline" 
                          className="w-full gap-2"
                          onClick={runAIAnalysis}
                          disabled={isAnalyzing || !comparisonId}
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
              </div>
            )}

            {/* Actions */}
            <div className="flex flex-col sm:flex-row gap-4 justify-center">
              <Button variant="outline" onClick={handleExportCSV}>
                <Download className="w-4 h-4 mr-2" />
                Export CSV
              </Button>
              <Button variant="outline" onClick={handleDownloadOverlay}>
                <ImageIcon className="w-4 h-4 mr-2" />
                Download Overlay
              </Button>
              <Button onClick={handleSaveToAccount}>
                <Save className="w-4 h-4 mr-2" />
                Save to Account
              </Button>
            </div>

            <div className="text-center">
              <Button variant="ghost" onClick={handleStartOver}>
                <ArrowLeft className="w-4 h-4 mr-2" />
                Start New Comparison
              </Button>
            </div>
          </div>
        )}

        {/* Save Step */}
        {step === "save" && (
          <div className="space-y-8 max-w-md mx-auto text-center">
            <div className="space-y-2">
              <Save className="w-12 h-12 mx-auto text-primary" />
              <h2 className="text-2xl font-bold font-display">Save Your Comparison</h2>
              <p className="text-muted-foreground">
                Create a free account to save this comparison and access more features.
              </p>
            </div>

            <Card>
              <CardContent className="pt-6 space-y-4">
                <div className="space-y-2 text-left">
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                    <span className="text-sm">Unlimited comparisons</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                    <span className="text-sm">Project organization</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                    <span className="text-sm">AI-powered change detection</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <CheckCircle2 className="w-4 h-4 text-green-500" />
                    <span className="text-sm">Cost & schedule analysis</span>
                  </div>
                </div>

                <div className="space-y-2">
                  <Link href={`/auth?return=/try-compare&save=${comparisonId}`}>
                    <Button className="w-full">
                      Create Free Account
                      <ArrowRight className="w-4 h-4 ml-2" />
                    </Button>
                  </Link>
                  <Link href={`/auth?return=/try-compare&save=${comparisonId}`}>
                    <Button variant="outline" className="w-full">
                      <LogIn className="w-4 h-4 mr-2" />
                      Sign In to Existing Account
                    </Button>
                  </Link>
                </div>
              </CardContent>
            </Card>

            <Button variant="ghost" onClick={() => setStep("results")}>
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Results
            </Button>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-8 mt-16">
        <div className="container mx-auto px-4 text-center text-sm text-muted-foreground">
          <p>BuildTrace - Drawing comparison for construction professionals</p>
        </div>
      </footer>
    </div>
  );
}
