import { useState } from "react";
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
  Check
} from "lucide-react";
import { Progress } from "@/components/ui/progress";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import logo from "@assets/BuildTrace_Logo_1767832159404.jpg";

export default function ProjectSetup() {
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [, setLocation] = useLocation();
  const [importMethod, setImportMethod] = useState<"upload" | "procore" | "acc" | null>(null);
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([]);
  const [connecting, setConnecting] = useState(false);
  const [connected, setConnected] = useState(false);

  const totalSteps = 4;
  const progress = (step / totalSteps) * 100;

  const handleNext = () => {
    if (step < totalSteps) {
      setStep(step + 1);
    } else {
      setLoading(true);
      setTimeout(() => {
        setLocation("/dashboard");
      }, 1500);
    }
  };

  const handleBack = () => {
    if (step > 1) setStep(step - 1);
  };

  const handleFileUpload = () => {
    setUploadedFiles([
      "IFC Set - Jan 2024.pdf",
      "Architectural Drawings.pdf",
      "MEP Coordination Set.pdf"
    ]);
  };

  const handleConnect = (platform: "procore" | "acc") => {
    setConnecting(true);
    setTimeout(() => {
      setConnecting(false);
      setConnected(true);
      setImportMethod(platform);
    }, 2000);
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
                        <Input id="name" placeholder="e.g., Memorial Hospital Expansion" />
                      </div>
                      <div className="space-y-2">
                        <Label htmlFor="number">Project Number</Label>
                        <Input id="number" placeholder="e.g., PRJ-2024-001" />
                      </div>
                    </div>
                    
                    <div className="space-y-2">
                      <Label htmlFor="address">Project Address</Label>
                      <div className="relative">
                        <MapPin className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                        <Input id="address" placeholder="123 Main Street, City, State" className="pl-9" />
                      </div>
                    </div>

                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Project Type</Label>
                        <Select>
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
                        <Select>
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
                      <Textarea id="description" placeholder="Brief description of the project scope..." rows={3} />
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
                        <Input placeholder="e.g., City Hospital Authority" />
                      </div>
                      <div className="space-y-2">
                        <Label>General Contractor</Label>
                        <Input placeholder="e.g., BuildCorps Construction" />
                      </div>
                    </div>

                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="space-y-2">
                        <Label>Architect of Record</Label>
                        <Input placeholder="e.g., Smith & Associates" />
                      </div>
                      <div className="space-y-2">
                        <Label>Project Manager</Label>
                        <Input placeholder="e.g., Alex Morgan" />
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
                        <Input placeholder="e.g., $45,000,000" />
                      </div>
                      <div className="space-y-2">
                        <Label>
                          <div className="flex items-center gap-2">
                            <Calendar className="w-4 h-4" /> Target Completion
                          </div>
                        </Label>
                        <Input type="date" />
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
                        <div 
                          onClick={handleFileUpload}
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
                                <FileText className="w-5 h-5 text-primary" />
                                <span className="flex-1 text-sm font-medium">{file}</span>
                                <CheckCircle2 className="w-5 h-5 text-green-500" />
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
                          <p className="font-semibold text-lg">Memorial Hospital Expansion</p>
                        </div>
                        <Badge>Healthcare</Badge>
                      </div>
                      
                      <Separator />
                      
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <p className="text-muted-foreground">Project Number</p>
                          <p className="font-medium">PRJ-2024-001</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Phase</p>
                          <p className="font-medium">Construction</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Contract Value</p>
                          <p className="font-medium">$45,000,000</p>
                        </div>
                        <div>
                          <p className="text-muted-foreground">Target Completion</p>
                          <p className="font-medium">Dec 2025</p>
                        </div>
                      </div>

                      <Separator />

                      <div>
                        <p className="text-muted-foreground text-sm mb-2">Imported Files</p>
                        <div className="flex flex-wrap gap-2">
                          <Badge variant="outline"><FileText className="w-3 h-3 mr-1" /> 3 Drawing Sets</Badge>
                          <Badge variant="outline"><FolderOpen className="w-3 h-3 mr-1" /> 142 Sheets</Badge>
                        </div>
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
