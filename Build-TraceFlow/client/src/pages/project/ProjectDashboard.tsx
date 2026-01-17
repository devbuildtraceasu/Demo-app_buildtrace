import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Link, useParams } from "wouter";
import { ArrowUpRight, Calendar, DollarSign, FileDiff, Layers, MoreHorizontal, Plus, Upload, FileText, Loader2, Settings } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import api from "@/lib/api";
import { useDrawingStatus } from "@/hooks/use-drawings";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useState, useMemo, useCallback } from "react";
import { useToast } from "@/hooks/use-toast";

export default function ProjectDashboard() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const { toast } = useToast();
  const queryClient = useQueryClient();

  // Settings modal state
  const [showSettings, setShowSettings] = useState(false);
  const [editedProject, setEditedProject] = useState<any>({});

  // Fetch project data
  const { data: project, isLoading: projectLoading } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.projects.get(projectId!),
    enabled: !!projectId,
  });

  // Fetch drawings for this project
  const { data: drawings } = useQuery({
    queryKey: ['project', projectId, 'drawings'],
    queryFn: () => api.drawings.listByProject(projectId!),
    enabled: !!projectId,
  });

  // Fetch comparisons for this project
  const { data: comparisons } = useQuery({
    queryKey: ['project', projectId, 'comparisons'],
    queryFn: () => api.comparisons.listByProject(projectId!),
    enabled: !!projectId,
  });

  // Fetch all blocks to get sheet IDs
  const { data: allBlocks } = useQuery({
    queryKey: ['all-blocks-for-dashboard'],
    queryFn: () => api.blocks.listAll(),
    enabled: !!projectId && !!comparisons && comparisons.length > 0,
    staleTime: 5 * 60 * 1000,
  });

  // Fetch all sheets to get sheet names
  const { data: allSheets } = useQuery({
    queryKey: ['all-sheets-for-dashboard', projectId],
    queryFn: async () => {
      if (!drawings || drawings.length === 0) return [];
      const sheetsPromises = drawings.map(d => 
        api.drawings.getSheets(d.id).catch(() => [])
      );
      const sheetsArrays = await Promise.all(sheetsPromises);
      return sheetsArrays.flat();
    },
    enabled: !!projectId && !!drawings && drawings.length > 0 && !!comparisons && comparisons.length > 0,
    staleTime: 5 * 60 * 1000,
  });

  // Create maps for sheet and block lookups
  const sheetMap = useMemo(() => {
    if (!allSheets) return {};
    const map: Record<string, { sheet_number?: string; title?: string; name?: string }> = {};
    allSheets.forEach(sheet => {
      map[sheet.id] = {
        sheet_number: sheet.sheet_number,
        title: sheet.title,
        name: sheet.sheet_number || sheet.title || 'Sheet',
      };
    });
    return map;
  }, [allSheets]);

  const blockToSheetMap = useMemo(() => {
    if (!allBlocks || !sheetMap) return {};
    const map: Record<string, string> = {};
    allBlocks.forEach(block => {
      if (block.sheet_id && sheetMap[block.sheet_id]) {
        map[block.id] = sheetMap[block.sheet_id].name || 'Sheet';
      }
    });
    return map;
  }, [allBlocks, sheetMap]);

  // Format comparison name with sheet names
  const formatComparisonName = useCallback((comparison: any) => {
    if (!blockToSheetMap || Object.keys(blockToSheetMap).length === 0) {
      return `Comparison #${comparison.id.slice(0, 8)}`;
    }
    
    // Note: drawing_a_id and drawing_b_id are actually block IDs (API bug)
    const sheetNameA = comparison.drawing_a_id ? blockToSheetMap[comparison.drawing_a_id] : null;
    const sheetNameB = comparison.drawing_b_id ? blockToSheetMap[comparison.drawing_b_id] : null;
    
    if (sheetNameA && sheetNameB) {
      return `${sheetNameA} old vs ${sheetNameB} new`;
    } else if (sheetNameA) {
      return `${sheetNameA} old vs Sheet B new`;
    } else if (sheetNameB) {
      return `Sheet A old vs ${sheetNameB} new`;
    }
    
    return `Comparison #${comparison.id.slice(0, 8)}`;
  }, [blockToSheetMap]);

  // Update project mutation
  const updateProjectMutation = useMutation({
    mutationFn: (data: any) => api.projects.update(projectId!, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['project', projectId] });
      toast({
        title: "Project Updated",
        description: "Project settings have been saved successfully.",
      });
      setShowSettings(false);
    },
    onError: (error) => {
      toast({
        title: "Update Failed",
        description: error instanceof Error ? error.message : "Failed to update project",
        variant: "destructive",
      });
    },
  });

  const handleOpenSettings = () => {
    setEditedProject({
      name: project?.name || '',
      description: project?.description || '',
      project_number: project?.project_number || '',
      address: project?.address || '',
      project_type: project?.project_type || '',
      phase: project?.phase || '',
    });
    setShowSettings(true);
  };

  const handleSaveSettings = () => {
    updateProjectMutation.mutate(editedProject);
  };

  if (projectLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </DashboardLayout>
    );
  }

  const projectName = project?.name || "Untitled Project";
  const projectType = project?.project_type || "";
  const projectAddress = project?.address || "";
  const drawingCount = drawings?.length || 0;
  const comparisonCount = comparisons?.length || 0;

  return (
    <DashboardLayout>
      <div className="p-8 max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-3xl font-bold font-display tracking-tight">{projectName}</h1>
              <Badge variant="outline" className="text-xs">Active</Badge>
            </div>
            <p className="text-muted-foreground">
              {[projectType, projectAddress].filter(Boolean).join(' • ') || 'No details'}
            </p>
          </div>
          <div className="flex gap-3">
             <Button variant="outline" onClick={handleOpenSettings}>
               <Settings className="mr-2 w-4 h-4" /> Project Settings
             </Button>
             <Link href={`/project/${projectId}/new-overlay`}>
               <Button>
                 <Plus className="mr-2 w-4 h-4" /> New Comparison
               </Button>
             </Link>
          </div>
        </div>

        {/* Stats Row */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard 
            title="Total Cost Impact" 
            value={comparisons?.reduce((sum, c) => sum + (parseFloat(c.total_cost_impact?.replace(/[^0-9.-]/g, '') || '0')), 0).toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }) || "$0"} 
            trend="from all comparisons" 
            trendUp={true}
            icon={<DollarSign className="w-4 h-4 text-muted-foreground" />} 
          />
          <StatCard 
            title="Schedule Drift" 
            value={comparisons?.reduce((sum, c) => sum + (parseInt(c.total_schedule_impact?.replace(/[^0-9]/g, '') || '0')), 0) + " Days" || "0 Days"} 
            trend="total impact" 
            trendUp={false}
            icon={<Calendar className="w-4 h-4 text-muted-foreground" />} 
          />
          <StatCard 
            title="Comparisons" 
            value={comparisonCount.toString()} 
            trend={comparisonCount > 0 ? "View all comparisons" : "None yet"} 
            icon={<FileDiff className="w-4 h-4 text-muted-foreground" />} 
          />
          <StatCard 
            title="Drawing Sets" 
            value={drawingCount.toString()} 
            trend={drawingCount > 0 ? `${drawings?.[0]?.name || 'Latest upload'}` : "Upload drawings to start"} 
            icon={<Layers className="w-4 h-4 text-muted-foreground" />} 
          />
        </div>

        {/* Main Content Area */}
        <div className="grid lg:grid-cols-3 gap-8">
          {/* Left Column - Recent Activity */}
          <div className="lg:col-span-2 space-y-6">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold font-display">Recent Comparisons</h2>
              <Button variant="ghost" size="sm">View All</Button>
            </div>
            
            <div className="space-y-4">
               {comparisons && comparisons.length > 0 ? (
                 [...comparisons]
                   .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                   .slice(0, 5)
                   .map((comparison) => (
                   <Link key={comparison.id} href={`/project/${projectId}/overlay/${comparison.id}`}>
                     <Card className="group hover:border-primary/50 transition-colors cursor-pointer">
                       <CardContent className="p-4 flex items-center justify-between">
                         <div className="flex items-center gap-4">
                           <div className="w-10 h-10 rounded-lg bg-primary/5 text-primary flex items-center justify-center">
                             <FileDiff className="w-5 h-5" />
                           </div>
                           <div>
                             <h3 className="font-semibold group-hover:text-primary transition-colors">
                               {formatComparisonName(comparison)}
                             </h3>
                             <p className="text-xs text-muted-foreground">
                               {new Date(comparison.created_at).toLocaleDateString()}
                             </p>
                           </div>
                         </div>
                         <div className="flex items-center gap-6">
                            <div className="text-right hidden sm:block">
                              <p className="text-sm font-medium">{comparison.change_count} Changes</p>
                              <p className="text-xs text-muted-foreground">{comparison.total_cost_impact || 'No cost data'}</p>
                            </div>
                            <Badge variant={comparison.status === "completed" ? "secondary" : "destructive"}>
                              {comparison.status}
                            </Badge>
                            <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                         </div>
                       </CardContent>
                     </Card>
                   </Link>
                 ))
               ) : (
                 <Card className="border-dashed">
                   <CardContent className="p-8 text-center">
                     <FileDiff className="w-12 h-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                     <h3 className="font-semibold mb-2">No comparisons yet</h3>
                     <p className="text-sm text-muted-foreground mb-4">
                       Upload drawings and run your first comparison to see results here.
                     </p>
                     <Link href={`/project/${projectId}/new-overlay`}>
                       <Button>
                         <Plus className="mr-2 w-4 h-4" /> New Comparison
                       </Button>
                     </Link>
                   </CardContent>
                 </Card>
               )}
            </div>

            {/* Drawing Sets Section */}
            <div className="pt-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold font-display">Drawing Sets</h2>
                <Link href={`/project/${projectId}/drawings`}>
                  <Button variant="outline" size="sm">
                    <Upload className="w-4 h-4 mr-2" /> Upload New
                  </Button>
                </Link>
              </div>
              
              <div className="grid md:grid-cols-2 gap-4">
                {drawings && drawings.length > 0 ? (
                  [...drawings]
                    .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                    .slice(0, 4)
                    .map((drawing) => (
                      <DrawingCard key={drawing.id} drawing={drawing} projectId={projectId} />
                    ))
                ) : (
                  <Card className="col-span-2 border-dashed">
                    <CardContent className="p-8 text-center">
                      <FileText className="w-12 h-12 mx-auto mb-4 text-muted-foreground opacity-50" />
                      <h3 className="font-semibold mb-2">No drawings uploaded</h3>
                      <p className="text-sm text-muted-foreground mb-4">
                        Upload your first drawing set to start comparing revisions.
                      </p>
                      <Link href={`/project/${projectId}/drawings`}>
                        <Button>
                          <Upload className="mr-2 w-4 h-4" /> Upload Drawings
                        </Button>
                      </Link>
                    </CardContent>
                  </Card>
                )}
              </div>
            </div>
          </div>

          {/* Right Column - Timeline */}
          <div className="space-y-6">
            <h2 className="text-xl font-bold font-display">Drawing Timeline</h2>
            <Card>
              <CardContent className="p-6">
                {drawings && drawings.length > 0 ? (
                  <>
                    <div className="space-y-8 relative before:absolute before:left-[15px] before:top-2 before:bottom-2 before:w-[2px] before:bg-border">
                      {[...drawings]
                        .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                        .slice(0, 4)
                        .map((drawing, i) => (
                        <div key={drawing.id} className="relative pl-8">
                           <div className={`absolute left-0 top-1 w-8 h-8 rounded-full border-4 border-background flex items-center justify-center z-10 ${i === 0 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
                             <div className="w-2 h-2 rounded-full bg-current" />
                           </div>
                           <div>
                             <p className={`font-semibold ${i === 0 ? "text-foreground" : "text-muted-foreground"}`}>
                               {drawing.name || drawing.filename}
                             </p>
                             <p className="text-xs text-muted-foreground">
                               {new Date(drawing.created_at).toLocaleDateString()}
                             </p>
                           </div>
                        </div>
                      ))}
                    </div>
                    <Button variant="outline" className="w-full mt-8">View Full Timeline</Button>
                  </>
                ) : (
                  <div className="text-center py-4">
                    <p className="text-sm text-muted-foreground">Upload drawings to see timeline</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Quick Actions */}
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-sm font-medium">Quick Actions</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <Link href={`/project/${projectId}/new-overlay`}>
                  <Button variant="outline" className="w-full justify-start gap-2">
                    <FileDiff className="w-4 h-4" /> Start New Comparison
                  </Button>
                </Link>
                <Link href={`/project/${projectId}/drawings`}>
                  <Button variant="outline" className="w-full justify-start gap-2">
                    <Upload className="w-4 h-4" /> Upload Drawing Set
                  </Button>
                </Link>
                <Link href={`/project/${projectId}/cost`}>
                  <Button variant="outline" className="w-full justify-start gap-2">
                    <DollarSign className="w-4 h-4" /> View Cost Report
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Project Settings Dialog */}
      <Dialog open={showSettings} onOpenChange={setShowSettings}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Project Settings</DialogTitle>
            <DialogDescription>
              Update project details and configuration.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-6 py-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="name">Project Name*</Label>
                <Input
                  id="name"
                  value={editedProject.name || ''}
                  onChange={(e) => setEditedProject((prev: any) => ({ ...prev, name: e.target.value }))}
                  placeholder="Enter project name"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="project_number">Project Number</Label>
                <Input
                  id="project_number"
                  value={editedProject.project_number || ''}
                  onChange={(e) => setEditedProject((prev: any) => ({ ...prev, project_number: e.target.value }))}
                  placeholder="e.g., PRJ-2024-001"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={editedProject.description || ''}
                onChange={(e) => setEditedProject((prev: any) => ({ ...prev, description: e.target.value }))}
                placeholder="Project description"
                rows={3}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="address">Address</Label>
              <Input
                id="address"
                value={editedProject.address || ''}
                onChange={(e) => setEditedProject((prev: any) => ({ ...prev, address: e.target.value }))}
                placeholder="Project location"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="project_type">Project Type</Label>
                <Input
                  id="project_type"
                  value={editedProject.project_type || ''}
                  onChange={(e) => setEditedProject((prev: any) => ({ ...prev, project_type: e.target.value }))}
                  placeholder="e.g., Commercial, Residential"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="phase">Phase</Label>
                <Input
                  id="phase"
                  value={editedProject.phase || ''}
                  onChange={(e) => setEditedProject((prev: any) => ({ ...prev, phase: e.target.value }))}
                  placeholder="e.g., Design, Construction"
                />
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setShowSettings(false)}
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveSettings}
              disabled={updateProjectMutation.isPending || !editedProject.name}
            >
              {updateProjectMutation.isPending ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...
                </>
              ) : (
                'Save Changes'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </DashboardLayout>
  );
}

function StatCard({ title, value, trend, icon, trendUp }: any) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium text-muted-foreground">{title}</CardTitle>
        {icon}
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold font-display">{value}</div>
        <p className={`text-xs ${trendUp === true ? "text-red-500" : trendUp === false ? "text-red-500" : "text-muted-foreground"} mt-1`}>
          {trend}
        </p>
      </CardContent>
    </Card>
  );
}

// Component to display drawing card with real-time status
function DrawingCard({ drawing, projectId }: { drawing: any; projectId?: string }) {
  const { data: status, isLoading: statusLoading } = useDrawingStatus(drawing.id);
  
  const sheetCount = status?.sheet_count ?? 0;
  const blockCount = status?.block_count ?? 0;
  const processingStatus = status?.status || 'pending';
  
  // Determine badge variant and text
  const getStatusBadge = () => {
    switch (processingStatus) {
      case 'completed':
        return { variant: 'secondary' as const, text: 'Complete' };
      case 'processing':
        return { variant: 'default' as const, text: 'Processing' };
      case 'failed':
        return { variant: 'destructive' as const, text: 'Failed' };
      default:
        return { variant: 'outline' as const, text: 'Pending' };
    }
  };
  
  const statusBadge = getStatusBadge();
  
  if (!projectId) {
    return null;
  }
  
  return (
    <Link href={`/project/${projectId}/drawings`}>
      <Card 
        className="hover:border-primary/30 transition-colors cursor-pointer group"
      >
      <CardContent className="p-4 flex items-center gap-4">
        <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center group-hover:bg-primary/10 transition-colors">
          {statusLoading || processingStatus === 'processing' ? (
            <Loader2 className="w-5 h-5 text-muted-foreground animate-spin" />
          ) : (
            <FileText className="w-5 h-5 text-muted-foreground group-hover:text-primary transition-colors" />
          )}
        </div>
        <div className="flex-1">
          <p className="font-medium group-hover:text-primary transition-colors">{drawing.name || drawing.filename}</p>
          <p className="text-xs text-muted-foreground">
            {sheetCount} {sheetCount === 1 ? 'sheet' : 'sheets'} • {blockCount} {blockCount === 1 ? 'block' : 'blocks'} • {new Date(drawing.created_at).toLocaleDateString()}
          </p>
        </div>
        <Badge variant={statusBadge.variant} className="text-xs capitalize">
          {statusBadge.text}
        </Badge>
      </CardContent>
    </Card>
    </Link>
  );
}
