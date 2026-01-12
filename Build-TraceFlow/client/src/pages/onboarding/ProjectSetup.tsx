import { useState, useRef, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useLocation } from "wouter";
import { motion, AnimatePresence } from "framer-motion";
import { 
  Upload, 
  FileText, 
  CheckCircle2, 
  ArrowRight, 
  ArrowLeft, 
  Loader2, 
  Building2, 
  MapPin,
  Cloud,
  Link2,
  FolderOpen,
  Users,
  Calendar,
  DollarSign,
  Check,
  X,
  AlertCircle
} from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { useToast } from "@/hooks/use-toast";
import api from "@/lib/api";
import logo from "@assets/BuildTrace_Logo_1767832159404.jpg";

interface UploadedFile {
  file: File;
  name: string;
  status: 'pending' | 'uploading' | 'processing' | 'complete' | 'error';
  progress: number;
  drawingId?: string;
  error?: string;
  sheetCount?: number;
  blockCount?: number;
}

export default function ProjectSetup() {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [, setLocation] = useLocation();
  const { toast } = useToast();
  
  // Project details (Step 1)
  const [projectName, setProjectName] = useState("");
  const [projectNumber, setProjectNumber] = useState("");
  const [projectAddress, setProjectAddress] = useState("");
  const [projectType, setProjectType] = useState("");
  const [projectPhase, setProjectPhase] = useState("");
  const [projectDescription, setProjectDescription] = useState("");
  
  // Team details (Step 2)
  const [ownerClient, setOwnerClient] = useState("");
  const [generalContractor, setGeneralContractor] = useState("");
  const [architect, setArchitect] = useState("");
  const [projectManager, setProjectManager] = useState("");
  const [contractValue, setContractValue] = useState("");
  const [targetCompletion, setTargetCompletion] = useState("");
  
  // Project ID (created after Step 1)
  const [projectId, setProjectId] = useState<string | null>(null);
  
  // File upload (Step 3)
  const [importMethod, setImportMethod] = useState<"upload" | "procore" | "acc" | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<UploadedFile[]>([]);
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const totalSteps = 4;
  const progress = (step / totalSteps) * 100;

  // Poll for processing status of uploaded drawings
  useEffect(() => {
    const pollDrawingStatus = async () => {
      const processingFiles = uploadedFiles.filter(f => f.status === 'processing' && f.drawingId);
      
      for (const file of processingFiles) {
        if (!file.drawingId) continue;
        
        try {
          const status = await api.drawings.getStatus(file.drawingId);
          
          setUploadedFiles(prev => prev.map(f => {
            if (f.drawingId !== file.drawingId) return f;
            
            if (status.status === 'completed') {
              return {
                ...f,
                status: 'complete',
                progress: 100,
                sheetCount: status.sheet_count,
                blockCount: status.block_count,
              };
            } else if (status.status === 'failed') {
              return {
                ...f,
                status: 'error',
                error: 'Processing failed',
              };
            } else {
              // Still processing - update progress based on status
              const newProgress = status.status === 'processing' 
                ? Math.min(90, (status.progress || 50))
                : f.progress;
              return {
                ...f,
                progress: newProgress,
                sheetCount: status.sheet_count,
                blockCount: status.block_count,
              };
            }
          }));
        } catch (error) {
          console.error('Error polling drawing status:', error);
        }
      }
    };

    const interval = setInterval(pollDrawingStatus, 3000);
    return () => clearInterval(interval);
  }, [uploadedFiles]);

  // Create project when moving from Step 1 to Step 2
  const handleCreateProject = async () => {
    if (!projectName.trim()) {
      toast({
        title: "Project name required",
        description: "Please enter a project name to continue.",
        variant: "destructive",
      });
      return false;
    }

    try {
      const project = await api.projects.create({
        name: projectName,
        description: projectDescription || undefined,
      });
      
      setProjectId(project.id);
      
      // Update project with additional details
      await api.projects.update(project.id, {
        project_number: projectNumber || undefined,
        address: projectAddress || undefined,
        project_type: projectType || undefined,
        phase: projectPhase || undefined,
      });
      
      toast({
        title: "Project created",
        description: "Your project has been created. Continue to add team details and drawings.",
      });
      
      return true;
    } catch (error) {
      console.error('Error creating project:', error);
      toast({
        title: "Error creating project",
        description: error instanceof Error ? error.message : "Failed to create project",
        variant: "destructive",
      });
      return false;
    }
  };

  const handleNext = async () => {
    if (step === 1) {
      // Create project before moving to Step 2
      const success = await handleCreateProject();
      if (!success) return;
    }
    
    if (step < totalSteps) {
      setStep(step + 1);
    } else {
      setLoading(true);
      // Final step - redirect to project dashboard
      setTimeout(() => {
        setLocation(projectId ? `/project/${projectId}` : "/dashboard");
      }, 1500);
    }
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    // Add files to list with pending status
    const newFiles: UploadedFile[] = Array.from(files).map(file => ({
      file,
      name: file.name,
      status: 'pending',
      progress: 0,
    }));
    
    setUploadedFiles(prev => [...prev, ...newFiles]);
    
    // Upload each file
    for (const uploadFile of newFiles) {
      await uploadSingleFile(uploadFile.file);
    }
    
    // Clear input
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const uploadSingleFile = async (file: File) => {
    if (!projectId) {
      toast({
        title: "Project not created",
        description: "Please complete Step 1 first to create a project.",
        variant: "destructive",
      });
      return;
    }

    // Update status to uploading
    setUploadedFiles(prev => prev.map(f => 
      f.file === file ? { ...f, status: 'uploading', progress: 10 } : f
    ));

    try {
      // Upload file directly
      const uploadResult = await api.uploads.uploadDirect(file, projectId);
      
      setUploadedFiles(prev => prev.map(f => 
        f.file === file ? { ...f, progress: 50 } : f
      ));

      // Create drawing record (this triggers Gemini processing)
      const drawing = await api.drawings.create({
        project_id: projectId,
        filename: file.name,
        name: file.name.replace(/\.[^/.]+$/, ''),
        uri: uploadResult.uri,
      });
      
      // Update to processing status
      setUploadedFiles(prev => prev.map(f => 
        f.file === file ? { 
          ...f, 
          status: 'processing', 
          progress: 60, 
          drawingId: drawing.id 
        } : f
      ));

      toast({
        title: "Upload complete",
        description: `${file.name} is now being processed by AI...`,
      });

    } catch (error) {
      console.error('Upload error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Upload failed';
      
      setUploadedFiles(prev => prev.map(f => 
        f.file === file ? { ...f, status: 'error', error: errorMessage } : f
      ));
      
      toast({
        title: "Upload failed",
        description: errorMessage,
        variant: "destructive",
      });
    }
  };

  const handleDropZoneClick = () => {
    fileInputRef.current?.click();
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    
    const files = e.dataTransfer.files;
    if (!files || files.length === 0) return;
    
    // Add files to list with pending status
    const newFiles: UploadedFile[] = Array.from(files).map(file => ({
      file,
      name: file.name,
      status: 'pending',
      progress: 0,
    }));
    
    setUploadedFiles(prev => [...prev, ...newFiles]);
    
    // Upload each file
    for (const uploadFile of newFiles) {
      await uploadSingleFile(uploadFile.file);
    }
  };

  const removeFile = (fileName: string) => {
    setUploadedFiles(prev => prev.filter(f => f.name !== fileName));
  };

  const handleConnect = (platform: "procore" | "acc") => {
    setConnecting(true);
    setTimeout(() => {
      setConnecting(false);
      setConnected(true);
      setImportMethod(platform);
    }, 2000);
  };

  const getStatusIcon = (file: UploadedFile) => {
    switch (file.status) {
      case 'complete':
        return <CheckCircle2 className="w-5 h-5 text-green-500" />;
      case 'error':
        return <AlertCircle className="w-5 h-5 text-red-500" />;
      case 'uploading':
      case 'processing':
        return <Loader2 className="w-5 h-5 animate-spin text-primary" />;
      default:
        return <FileText className="w-5 h-5 text-primary" />;
    }
  };

  const getStatusText = (file: UploadedFile) => {
    switch (file.status) {
      case 'uploading':
        return `Uploading... ${file.progress}%`;
      case 'processing':
        return `AI Processing... ${file.progress}%`;
      case 'complete':
        return `${file.sheetCount || 0} sheets, ${file.blockCount || 0} blocks`;
      case 'error':
        return file.error || 'Error';
      default:
        return 'Pending';
    }
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Header */}
      <header className="h-16 border-b border-border flex items-center px-8 bg-background/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="flex items-center gap-2 mr-8">
          <img src={logo} alt="BuildTrace" className="w-8 h-8 rounded-md" />
          <span className="font-bold font-display">BuildTrace</span>
        </div>
        <div className="flex-1 max-w-md">
          <div className="flex justify-between text-xs font-medium text-muted-foreground mb-2">
            <span>Project Setup</span>
            <span>Step {step} of {totalSteps}</span>
          </div>
          <Progress value={progress} className="h-1.5" />
        </div>
      </header>

      {/* Main Content */}
      <main className="flex-1 flex items-center justify-center p-8">
        <div className="w-full max-w-2xl">
          <AnimatePresence mode="wait">
            {step === 1 && (
              <motion.div
                key="step1"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
              >
                <Card className="border-border shadow-lg">
                  <CardHeader className="text-center pb-2">
                    <div className="mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-4">
                      <Building2 className="w-6 h-6 text-primary" />
                    </div>
                    <CardTitle className="text-2xl font-display">Project Details</CardTitle>
                    <CardDescription>Tell us about your construction project</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6 pt-4">
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="name">Project Name *</Label>
                        <Input 
                          id="name" 
                          placeholder="e.g., Memorial Hospital Expansion" 
                          value={projectName}
                          onChange={(e) => setProjectName(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="number">Project Number</Label>
                        <Input 
                          id="number" 
                          placeholder="e.g., PRJ-2024-001" 
                          value={projectNumber}
                          onChange={(e) => setProjectNumber(e.target.value)}
                        />
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="address">Project Address</Label>
                      <div className="relative">
                        <MapPin className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                        <Input 
                          id="address" 
                          placeholder="123 Main Street, City, State" 
                          className="pl-9" 
                          value={projectAddress}
                          onChange={(e) => setProjectAddress(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Project Type</Label>
                        <Select value={projectType} onValueChange={setProjectType}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select type" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="healthcare">Healthcare</SelectItem>
                            <SelectItem value="commercial">Commercial</SelectItem>
                            <SelectItem value="residential">Residential</SelectItem>
                            <SelectItem value="industrial">Industrial</SelectItem>
                            <SelectItem value="infrastructure">Infrastructure</SelectItem>
                            <SelectItem value="education">Education</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="space-y-2">
                        <Label>Project Phase</Label>
                        <Select value={projectPhase} onValueChange={setProjectPhase}>
                          <SelectTrigger>
                            <SelectValue placeholder="Select phase" />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="preconstruction">Preconstruction</SelectItem>
                            <SelectItem value="construction">Construction</SelectItem>
                            <SelectItem value="closeout">Closeout</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <Label htmlFor="description">Project Description</Label>
                      <Textarea 
                        id="description" 
                        placeholder="Brief description of the project scope..." 
                        rows={3}
                        value={projectDescription}
                        onChange={(e) => setProjectDescription(e.target.value)}
                      />
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {step === 2 && (
              <motion.div
                key="step2"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
              >
                <Card className="border-border shadow-lg">
                  <CardHeader className="text-center pb-2">
                    <div className="mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-4">
                      <Users className="w-6 h-6 text-primary" />
                    </div>
                    <CardTitle className="text-2xl font-display">Project Team & Budget</CardTitle>
                    <CardDescription>Add team details and financial information</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6 pt-4">
                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Owner / Client</Label>
                        <Input 
                          placeholder="e.g., City Hospital Authority" 
                          value={ownerClient}
                          onChange={(e) => setOwnerClient(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>General Contractor</Label>
                        <Input 
                          placeholder="e.g., BuildCorps Construction" 
                          value={generalContractor}
                          onChange={(e) => setGeneralContractor(e.target.value)}
                        />
                      </div>
                    </div>

                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Architect of Record</Label>
                        <Input 
                          placeholder="e.g., Smith & Associates" 
                          value={architect}
                          onChange={(e) => setArchitect(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>Project Manager</Label>
                        <Input 
                          placeholder="e.g., Alex Morgan" 
                          value={projectManager}
                          onChange={(e) => setProjectManager(e.target.value)}
                        />
                      </div>
                    </div>

                    <Separator />

                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>
                          <div className="flex items-center gap-2">
                            <DollarSign className="w-4 h-4" /> Contract Value
                          </div>
                        </Label>
                        <Input 
                          placeholder="e.g., $45,000,000" 
                          value={contractValue}
                          onChange={(e) => setContractValue(e.target.value)}
                        />
                      </div>
                      <div className="space-y-2">
                        <Label>
                          <div className="flex items-center gap-2">
                            <Calendar className="w-4 h-4" /> Target Completion
                          </div>
                        </Label>
                        <Input 
                          type="date" 
                          value={targetCompletion}
                          onChange={(e) => setTargetCompletion(e.target.value)}
                        />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {step === 3 && (
              <motion.div
                key="step3"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
              >
                <Card className="border-border shadow-lg">
                  <CardHeader className="text-center pb-2">
                    <div className="mx-auto w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mb-4">
                      <FolderOpen className="w-6 h-6 text-primary" />
                    </div>
                    <CardTitle className="text-2xl font-display">Import Drawings</CardTitle>
                    <CardDescription>Upload files or connect to your project management platform</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6 pt-4">
                    {/* Import Method Selection */}
                    <div className="grid md:grid-cols-3 gap-4">
                      <div 
                        onClick={() => setImportMethod("upload")}
                        className={`
                          p-4 rounded-xl border-2 cursor-pointer transition-all text-center
                          ${importMethod === "upload" ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'}
                        `}
                      >
                        <Upload className="w-8 h-8 mx-auto mb-2 text-primary" />
                        <p className="font-medium text-sm">Upload Files</p>
                        <p className="text-xs text-muted-foreground mt-1">PDF, DWG, DXF</p>
                      </div>
                      
                      <div 
                        onClick={() => handleConnect("procore")}
                        className={`
                          p-4 rounded-xl border-2 cursor-pointer transition-all text-center relative
                          ${importMethod === "procore" ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'}
                        `}
                      >
                        {connected && importMethod === "procore" && (
                          <Badge className="absolute -top-2 -right-2 bg-green-500">
                            <Check className="w-3 h-3" />
                          </Badge>
                        )}
                        <Cloud className="w-8 h-8 mx-auto mb-2 text-orange-500" />
                        <p className="font-medium text-sm">Procore</p>
                        <p className="text-xs text-muted-foreground mt-1">Connect & sync</p>
                      </div>
                      
                      <div 
                        onClick={() => handleConnect("acc")}
                        className={`
                          p-4 rounded-xl border-2 cursor-pointer transition-all text-center relative
                          ${importMethod === "acc" ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'}
                        `}
                      >
                        {connected && importMethod === "acc" && (
                          <Badge className="absolute -top-2 -right-2 bg-green-500">
                            <Check className="w-3 h-3" />
                          </Badge>
                        )}
                        <Link2 className="w-8 h-8 mx-auto mb-2 text-blue-500" />
                        <p className="font-medium text-sm">Autodesk CC</p>
                        <p className="text-xs text-muted-foreground mt-1">Connect & sync</p>
                      </div>
                    </div>

                    {connecting && (
                      <div className="text-center py-8">
                        <Loader2 className="w-8 h-8 animate-spin mx-auto text-primary mb-4" />
                        <p className="text-muted-foreground">Connecting to platform...</p>
                      </div>
                    )}

                    {importMethod === "upload" && !connecting && (
                      <div className="space-y-4">
                        {/* Hidden file input */}
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept=".pdf,.dwg,.dxf"
                          multiple
                          onChange={handleFileSelect}
                          className="hidden"
                        />
                        
                        <div 
                          onClick={handleDropZoneClick}
                          onDragOver={handleDragOver}
                          onDrop={handleDrop}
                          className="border-2 border-dashed border-border rounded-xl p-8 text-center hover:border-primary/50 hover:bg-muted/20 transition-all cursor-pointer"
                        >
                          <Upload className="w-10 h-10 mx-auto mb-4 text-muted-foreground" />
                          <p className="font-medium mb-1">Drop files here or click to browse</p>
                          <p className="text-sm text-muted-foreground">PDF, DWG, DXF up to 500MB each</p>
                        </div>

                        {uploadedFiles.length > 0 && (
                          <div className="space-y-2">
                            <p className="text-sm font-medium text-muted-foreground">Uploaded Files</p>
                            {uploadedFiles.map((file, i) => (
                              <div key={i} className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg border border-border">
                                {getStatusIcon(file)}
                                <div className="flex-1 min-w-0">
                                  <p className="text-sm font-medium truncate">{file.name}</p>
                                  <p className="text-xs text-muted-foreground">{getStatusText(file)}</p>
                                  {(file.status === 'uploading' || file.status === 'processing') && (
                                    <Progress value={file.progress} className="h-1 mt-1" />
                                  )}
                                </div>
                                {file.status === 'complete' && (
                                  <CheckCircle2 className="w-5 h-5 text-green-500 shrink-0" />
                                )}
                                {file.status === 'error' && (
                                  <button 
                                    onClick={() => removeFile(file.name)}
                                    className="p-1 hover:bg-muted rounded shrink-0"
                                  >
                                    <X className="w-4 h-4 text-muted-foreground" />
                                  </button>
                                )}
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {connected && (importMethod === "procore" || importMethod === "acc") && (
                      <div className="space-y-4">
                        <div className="p-4 bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg">
                          <div className="flex items-center gap-2 text-green-700 dark:text-green-400">
                            <CheckCircle2 className="w-5 h-5" />
                            <span className="font-medium">Connected to {importMethod === "procore" ? "Procore" : "Autodesk Construction Cloud"}</span>
                          </div>
                        </div>
                        
                        <div className="space-y-2">
                          <Label>Select Project to Sync</Label>
                          <Select>
                            <SelectTrigger>
                              <SelectValue placeholder="Choose a project..." />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="hospital">Memorial Hospital Expansion</SelectItem>
                              <SelectItem value="downtown">Downtown Lab Complex</SelectItem>
                              <SelectItem value="seaport">Seaport Multifamily</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>

                        <div className="space-y-2">
                          <Label>Drawing Folders to Import</Label>
                          <div className="space-y-2">
                            {["Current Construction Docs", "ASI & Bulletins", "Shop Drawings"].map((folder, i) => (
                              <div key={i} className="flex items-center gap-3 p-3 bg-muted/30 rounded-lg border border-border">
                                <input type="checkbox" defaultChecked className="rounded" />
                                <FolderOpen className="w-4 h-4 text-muted-foreground" />
                                <span className="text-sm">{folder}</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      </div>
                    )}
                  </CardContent>
                </Card>
              </motion.div>
            )}

            {step === 4 && (
              <motion.div
                key="step4"
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
              >
                <Card className="border-border shadow-lg">
                  <CardHeader className="text-center pb-2">
                    <div className="mx-auto w-14 h-14 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mb-4">
                      <CheckCircle2 className="w-8 h-8 text-green-600" />
                    </div>
                    <CardTitle className="text-2xl font-display">Project Ready!</CardTitle>
                    <CardDescription>Review your project details before creating</CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-6 pt-4">
                    <div className="bg-muted/30 rounded-xl p-6 space-y-4">
                      <div className="flex justify-between items-start">
                        <div>
                          <p className="text-xs text-muted-foreground uppercase tracking-wider">Project Name</p>
                          <p className="font-semibold text-lg">{projectName || "Untitled Project"}</p>
                        </div>
                        {projectType && (
                          <Badge className="capitalize">{projectType}</Badge>
                        )}
                      </div>
                      
                      <Separator />
                      
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-muted-foreground">Project Number</p>
                          <p className="font-medium">{projectNumber || "—"}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Phase</p>
                          <p className="font-medium capitalize">{projectPhase || "—"}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Contract Value</p>
                          <p className="font-medium">{contractValue || "—"}</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Target Completion</p>
                          <p className="font-medium">{targetCompletion || "—"}</p>
                        </div>
                      </div>

                      <Separator />

                      <div>
                        <p className="text-muted-foreground text-sm mb-2">Imported Files</p>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="outline">
                            <FileText className="w-3 h-3 mr-1" /> 
                            {uploadedFiles.filter(f => f.status === 'complete').length} Drawing Sets
                          </Badge>
                          <Badge variant="outline">
                            <FolderOpen className="w-3 h-3 mr-1" /> 
                            {uploadedFiles.filter(f => f.status === 'complete').reduce((sum, f) => sum + (f.sheetCount || 0), 0)} Sheets
                          </Badge>
                          <Badge variant="outline">
                            {uploadedFiles.filter(f => f.status === 'complete').reduce((sum, f) => sum + (f.blockCount || 0), 0)} Blocks
                          </Badge>
                        </div>
                        
                        {uploadedFiles.some(f => f.status === 'processing') && (
                          <div className="mt-3 p-3 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                            <div className="flex items-center gap-2 text-amber-700 dark:text-amber-400">
                              <Loader2 className="w-4 h-4 animate-spin" />
                              <span className="text-sm">
                                {uploadedFiles.filter(f => f.status === 'processing').length} file(s) still processing...
                              </span>
                            </div>
                          </div>
                        )}
                      </div>
                    </div>

                    <p className="text-center text-sm text-muted-foreground">
                      You can start comparing drawings and running overlays after the project is created.
                    </p>
                  </CardContent>
                </Card>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Navigation */}
          <div className="flex justify-between mt-8">
            <Button 
              variant="outline" 
              onClick={handleBack}
              disabled={step === 1}
              className="gap-2"
            >
              <ArrowLeft className="w-4 h-4" /> Back
            </Button>
            <Button onClick={handleNext} disabled={loading} className="gap-2 min-w-[140px]">
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" /> Creating...
                </>
              ) : step === totalSteps ? (
                <>
                  Create Project <CheckCircle2 className="w-4 h-4" />
                </>
              ) : (
                <>
                  Continue <ArrowRight className="w-4 h-4" />
                </>
              )}
            </Button>
          </div>
        </div>
      </main>
    </div>
  );
}
