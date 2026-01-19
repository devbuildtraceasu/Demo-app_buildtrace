import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { 
  Upload, 
  FileText, 
  FolderOpen, 
  Search, 
  Filter,
  Grid3X3,
  List,
  ChevronRight,
  Calendar,
  Layers,
  Eye,
  Download,
  MoreVertical,
  Plus,
  CloudUpload,
  LinkIcon,
  Loader2,
  ExternalLink
} from "lucide-react";
import { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { useParams, Link } from "wouter";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { useDrawingStatus, useSheets } from "@/hooks/use-drawings";
import { ScrollArea } from "@/components/ui/scroll-area";

export default function Drawings() {
  const params = useParams();
  const projectId = params?.id;
  const [viewMode, setViewMode] = useState<"grid" | "list">("list");
  const [viewerOpen, setViewerOpen] = useState(false);
  const [viewerImage, setViewerImage] = useState<{ uri: string; title: string; description?: string } | null>(null);
  const [sheetsDialogOpen, setSheetsDialogOpen] = useState(false);
  const [selectedDrawingId, setSelectedDrawingId] = useState<string | null>(null);

  // Mock data for demo purposes
  const mockDrawingSets = [
    { 
      id: "v1", 
      name: "IFC Set", 
      date: "Jan 12, 2024", 
      sheets: 142, 
      disciplines: ["Architectural", "Structural", "MEP"],
      status: "Complete"
    },
    { 
      id: "v2", 
      name: "Bulletin 01", 
      date: "Jan 20, 2024", 
      sheets: 12, 
      disciplines: ["Architectural", "Structural"],
      status: "Complete"
    },
    { 
      id: "v3", 
      name: "Bulletin 02", 
      date: "Feb 01, 2024", 
      sheets: 8, 
      disciplines: ["Architectural", "Mechanical"],
      status: "Complete"
    },
    { 
      id: "v4", 
      name: "Bulletin 03", 
      date: "Feb 15, 2024", 
      sheets: 15, 
      disciplines: ["Architectural", "Electrical", "Plumbing"],
      status: "Processing"
    },
  ];

  const mockSheets = [
    { id: "A-101", name: "First Floor Plan", discipline: "Architectural", set: "Bulletin 03", date: "Feb 15", blockId: "mock-1", drawingId: "v4", uri: null },
    { id: "A-102", name: "Second Floor Plan", discipline: "Architectural", set: "Bulletin 03", date: "Feb 15", blockId: "mock-2", drawingId: "v4", uri: null },
    { id: "A-201", name: "Building Elevations", discipline: "Architectural", set: "Bulletin 03", date: "Feb 15", blockId: "mock-3", drawingId: "v4", uri: null },
    { id: "S-101", name: "Foundation Plan", discipline: "Structural", set: "IFC Set", date: "Jan 12", blockId: "mock-4", drawingId: "v1", uri: null },
    { id: "S-102", name: "Framing Plan Level 2", discipline: "Structural", set: "Bulletin 01", date: "Jan 20", blockId: "mock-5", drawingId: "v2", uri: null },
    { id: "M-101", name: "HVAC Floor Plan L1", discipline: "Mechanical", set: "Bulletin 02", date: "Feb 01", blockId: "mock-6", drawingId: "v3", uri: null },
    { id: "E-101", name: "Electrical Floor Plan L1", discipline: "Electrical", set: "Bulletin 03", date: "Feb 15", blockId: "mock-7", drawingId: "v4", uri: null },
    { id: "P-101", name: "Plumbing Floor Plan L1", discipline: "Plumbing", set: "Bulletin 03", date: "Feb 15", blockId: "mock-8", drawingId: "v4", uri: null },
  ];

  // Fetch real drawings from API
  const { data: drawings, isLoading } = useQuery({
    queryKey: ['project', projectId, 'drawings'],
    queryFn: () => api.drawings.listByProject(projectId!),
    enabled: !!projectId,
  });

  // Fetch sheets from API (blocks with type "Plan")
  const { data: allSheets } = useQuery({
    queryKey: ['project', projectId, 'sheets'],
    queryFn: async () => {
      if (!drawings || drawings.length === 0) return [];
      // Fetch sheets for each drawing
      const sheetsPromises = drawings.map(d => 
        api.drawings.getStatus(d.id).then(status => 
          status.blocks?.filter(b => b.type === 'Plan').map(b => ({
            ...b,
            drawingId: d.id,
            drawingName: d.name,
          })) || []
        ).catch(() => [])
      );
      const results = await Promise.all(sheetsPromises);
      return results.flat();
    },
    enabled: !!drawings && drawings.length > 0,
  });

  // Fetch all blocks from API
  const { data: allBlocks } = useQuery({
    queryKey: ['project', projectId, 'all-blocks'],
    queryFn: async () => {
      if (!drawings || drawings.length === 0) return [];
      // Fetch all blocks for each drawing
      const blocksPromises = drawings.map(d => 
        api.drawings.getBlocks(d.id).then(blocks => 
          blocks.map(b => ({
            ...b,
            drawingId: d.id,
            drawingName: d.name || d.filename,
          }))
        ).catch(() => [])
      );
      const results = await Promise.all(blocksPromises);
      return results.flat();
    },
    enabled: !!drawings && drawings.length > 0,
  });

  // Combine mock and real drawing sets (status will be fetched per drawing in DrawingSetCard)
  const apiDrawingSets = drawings?.map(d => ({
    id: d.id,
    name: d.name || `Drawing ${d.id.slice(0, 8)}`,
    date: new Date(d.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }),
    drawing: d, // Store full drawing object for status fetching
    disciplines: ['Architectural'],
  })) || [];
  const drawingSets = [...mockDrawingSets, ...apiDrawingSets];

  // Combine mock and real sheets
  const apiSheets = allSheets?.map((s, idx) => ({
    id: `Sheet-${idx + 1}`,
    blockId: s.id,
    name: s.description || 'Plan Block',
    discipline: 'Architectural',
    set: s.drawingName || 'Unknown',
    drawingId: s.drawingId,
    date: 'Recent',
    uri: s.uri,
  })) || [];
  const sheets = [...mockSheets, ...apiSheets];

  const hasDrawings = drawingSets.length > 0;

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </DashboardLayout>
    );
  }

  if (!hasDrawings) {
    return (
      <DashboardLayout>
        <div className="p-8 max-w-4xl mx-auto">
          <div className="text-center py-16">
            <div className="w-24 h-24 rounded-full bg-muted/50 flex items-center justify-center mx-auto mb-6">
              <Layers className="w-12 h-12 text-muted-foreground" />
            </div>
            <h1 className="text-2xl font-bold font-display mb-2">No Drawings Yet</h1>
            <p className="text-muted-foreground mb-8 max-w-md mx-auto">
              Upload your drawing sets to get started with comparisons and change detection.
            </p>
            
            <div className="grid md:grid-cols-3 gap-4 max-w-2xl mx-auto">
              <Link href={`/project/${projectId}/new-overlay`}>
                <Card className="cursor-pointer hover:border-primary/50 transition-all group">
                  <CardContent className="p-6 text-center">
                    <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mx-auto mb-3 group-hover:bg-primary/20 transition-colors">
                      <Upload className="w-6 h-6 text-primary" />
                    </div>
                    <p className="font-medium text-sm mb-1">Upload Files</p>
                    <p className="text-xs text-muted-foreground">PDF, DWG, DXF</p>
                  </CardContent>
                </Card>
              </Link>
              
              <Card className="cursor-pointer hover:border-primary/50 transition-all group opacity-50">
                <CardContent className="p-6 text-center">
                  <div className="w-12 h-12 rounded-lg bg-orange-100 flex items-center justify-center mx-auto mb-3 group-hover:bg-orange-200 transition-colors">
                    <CloudUpload className="w-6 h-6 text-orange-600" />
                  </div>
                  <p className="font-medium text-sm mb-1">Connect Procore</p>
                  <p className="text-xs text-muted-foreground">Coming soon</p>
                </CardContent>
              </Card>
              
              <Card className="cursor-pointer hover:border-primary/50 transition-all group opacity-50">
                <CardContent className="p-6 text-center">
                  <div className="w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center mx-auto mb-3 group-hover:bg-blue-200 transition-colors">
                    <LinkIcon className="w-6 h-6 text-blue-600" />
                  </div>
                  <p className="font-medium text-sm mb-1">Connect ACC</p>
                  <p className="text-xs text-muted-foreground">Coming soon</p>
                </CardContent>
              </Card>
            </div>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="p-8 space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold font-display tracking-tight">Drawings</h1>
            <p className="text-muted-foreground mt-1">Manage drawing sets and individual sheets</p>
          </div>
          <Button className="gap-2">
            <Plus className="w-4 h-4" /> Upload Drawings
          </Button>
        </div>

        <Tabs defaultValue="sets" className="w-full">
          <div className="flex items-center justify-between mb-4">
            <TabsList>
              <TabsTrigger value="sets">Drawing Sets</TabsTrigger>
              <TabsTrigger value="sheets">All Sheets</TabsTrigger>
              <TabsTrigger value="blocks">All Blocks</TabsTrigger>
            </TabsList>
            
            <div className="flex items-center gap-2">
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input placeholder="Search drawings..." className="pl-9" />
              </div>
              <Button variant="outline" size="icon">
                <Filter className="w-4 h-4" />
              </Button>
              <div className="border-l border-border h-6 mx-1" />
              <Button 
                variant={viewMode === "grid" ? "secondary" : "ghost"} 
                size="icon"
                onClick={() => setViewMode("grid")}
              >
                <Grid3X3 className="w-4 h-4" />
              </Button>
              <Button 
                variant={viewMode === "list" ? "secondary" : "ghost"} 
                size="icon"
                onClick={() => setViewMode("list")}
              >
                <List className="w-4 h-4" />
              </Button>
            </div>
          </div>

          <TabsContent value="sets">
            {viewMode === "grid" ? (
              <div className="grid md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
                {drawingSets.map((set) => (
                  <DrawingSetCard 
                    key={set.id} 
                    set={set} 
                    projectId={projectId}
                    onViewSheets={(drawingId) => {
                      setSelectedDrawingId(drawingId);
                      setSheetsDialogOpen(true);
                    }}
                  />
                ))}
              </div>
            ) : (
              <Card>
                <div className="divide-y divide-border">
                  {drawingSets.map((set) => (
                    <DrawingSetRow 
                      key={set.id} 
                      set={set} 
                      projectId={projectId}
                      onViewSheets={(drawingId) => {
                        setSelectedDrawingId(drawingId);
                        setSheetsDialogOpen(true);
                      }}
                    />
                  ))}
                </div>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="sheets">
            <Card>
              <div className="divide-y divide-border">
                {sheets.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground">
                    <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>No sheets found. Upload drawings to see extracted sheets.</p>
                  </div>
                ) : (
                  sheets.map((sheet) => (
                    <div key={sheet.blockId || sheet.id} className="p-4 flex items-center justify-between hover:bg-muted/30 transition-colors">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
                          <FileText className="w-5 h-5 text-muted-foreground" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-sm font-medium">{sheet.id}</span>
                            <span className="text-sm text-muted-foreground">-</span>
                            <span className="text-sm">{sheet.name}</span>
                          </div>
                          <p className="text-xs text-muted-foreground">{sheet.set} • {sheet.date}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge variant="outline" className="text-[10px]">{sheet.discipline}</Badge>
                        {sheet.uri ? (
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="h-7 gap-1"
                            onClick={() => {
                              setViewerImage({ uri: sheet.uri!, title: sheet.name, description: `${sheet.set} • ${sheet.date}` });
                              setViewerOpen(true);
                            }}
                          >
                            <Eye className="w-3 h-3" /> View
                          </Button>
                        ) : (
                          <Link href={`/project/${projectId}/drawing/${sheet.drawingId}`}>
                            <Button variant="ghost" size="sm" className="h-7 gap-1">
                              <Eye className="w-3 h-3" /> View
                            </Button>
                          </Link>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </TabsContent>

          <TabsContent value="blocks">
            <Card>
              <div className="divide-y divide-border">
                {!allBlocks || allBlocks.length === 0 ? (
                  <div className="p-8 text-center text-muted-foreground">
                    <FileText className="w-8 h-8 mx-auto mb-2 opacity-50" />
                    <p>No blocks found. Upload drawings to see extracted blocks.</p>
                  </div>
                ) : (
                  allBlocks.map((block) => (
                    <div key={block.id} className="p-4 flex items-center justify-between hover:bg-muted/30 transition-colors">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
                          <FileText className="w-5 h-5 text-muted-foreground" />
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium">{block.description || block.type || 'Block'}</span>
                            {block.type && (
                              <>
                                <span className="text-sm text-muted-foreground">•</span>
                                <Badge variant="outline" className="text-[10px]">{block.type}</Badge>
                              </>
                            )}
                          </div>
                          <p className="text-xs text-muted-foreground">
                            {block.drawingName || 'Unknown Drawing'} • {new Date(block.created_at).toLocaleDateString()}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        {block.uri ? (
                          <Button 
                            variant="ghost" 
                            size="sm" 
                            className="h-7 gap-1"
                            onClick={() => {
                              setViewerImage({ 
                                uri: block.uri!, 
                                title: block.description || block.type || 'Block',
                                description: `${block.type || 'Block'} • ${block.drawingName || 'Unknown Drawing'}`
                              });
                              setViewerOpen(true);
                            }}
                          >
                            <Eye className="w-3 h-3" /> View
                          </Button>
                        ) : (
                          <Button variant="ghost" size="sm" className="h-7 gap-1" disabled>
                            <Eye className="w-3 h-3" /> No Image
                          </Button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </Card>
          </TabsContent>
        </Tabs>
        
        {/* Image Viewer Modal */}
        <Dialog open={viewerOpen} onOpenChange={setViewerOpen}>
          <DialogContent className="max-w-4xl max-h-[90vh] overflow-auto">
            <DialogHeader>
              <DialogTitle>{viewerImage?.title}</DialogTitle>
              {viewerImage?.description && (
                <DialogDescription>{viewerImage.description}</DialogDescription>
              )}
            </DialogHeader>
            {viewerImage && (
              <div className="mt-4">
                <img 
                  src={viewerImage.uri} 
                  alt={viewerImage.title}
                  className="w-full h-auto rounded-lg border"
                  onError={(e) => {
                    (e.target as HTMLImageElement).src = 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300"><rect width="400" height="300" fill="%23f0f0f0"/><text x="50%25" y="50%25" text-anchor="middle" dy=".3em" fill="%23999">Image not available</text></svg>';
                  }}
                />
              </div>
            )}
          </DialogContent>
        </Dialog>

        {/* Sheets and Blocks Dialog */}
        <SheetsDialog 
          open={sheetsDialogOpen}
          onOpenChange={setSheetsDialogOpen}
          drawingId={selectedDrawingId}
        />
      </div>
    </DashboardLayout>
  );
}

// Sheets Dialog Component
function SheetsDialog({ open, onOpenChange, drawingId }: { open: boolean; onOpenChange: (open: boolean) => void; drawingId: string | null }) {
  const { data: sheets, isLoading: sheetsLoading } = useSheets(drawingId);
  
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-4xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Sheets and Blocks</DialogTitle>
          <DialogDescription>
            View all sheets and their corresponding blocks for this drawing
          </DialogDescription>
        </DialogHeader>
        <ScrollArea className="flex-1 -mx-6 px-6">
          {sheetsLoading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            </div>
          ) : !sheets || sheets.length === 0 ? (
            <div className="text-center py-12 text-muted-foreground">
              <FileText className="w-12 h-12 mx-auto mb-4 opacity-50" />
              <p>No sheets found for this drawing.</p>
            </div>
          ) : (
            <div className="space-y-4 py-4">
              {sheets.map((sheet) => (
                <SheetBlockCard key={sheet.id} sheet={sheet} />
              ))}
            </div>
          )}
        </ScrollArea>
      </DialogContent>
    </Dialog>
  );
}

// Sheet Block Card Component
function SheetBlockCard({ sheet }: { sheet: any }) {
  const { data: blocks, isLoading: blocksLoading } = useQuery({
    queryKey: ['sheet', sheet.id, 'blocks'],
    queryFn: () => api.blocks.listBySheet(sheet.id),
    enabled: !!sheet.id,
  });

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-base">{sheet.sheet_number || sheet.title || 'Unnamed Sheet'}</CardTitle>
            {sheet.title && sheet.sheet_number && (
              <CardDescription className="mt-1">{sheet.title}</CardDescription>
            )}
          </div>
          <Badge variant="outline">{sheet.discipline || 'Unknown'}</Badge>
        </div>
      </CardHeader>
      <CardContent>
        {blocksLoading ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="w-4 h-4 animate-spin" />
            Loading blocks...
          </div>
        ) : !blocks || blocks.length === 0 ? (
          <p className="text-sm text-muted-foreground">No blocks found for this sheet.</p>
        ) : (
          <div className="space-y-2">
            <p className="text-sm font-medium mb-2">{blocks.length} {blocks.length === 1 ? 'block' : 'blocks'}:</p>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
              {blocks.map((block: any) => (
                <div 
                  key={block.id} 
                  className="p-2 rounded border bg-muted/30 text-sm"
                >
                  <div className="font-medium">{block.name || block.type || 'Unnamed Block'}</div>
                  {block.type && (
                    <div className="text-xs text-muted-foreground mt-1">{block.type}</div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Component for drawing set card with real-time status
function DrawingSetCard({ set, projectId, onViewSheets }: { set: any; projectId?: string; onViewSheets?: (drawingId: string) => void }) {
  const isMock = !set.drawing;
  const { data: status, isLoading: statusLoading } = useDrawingStatus(isMock ? undefined : set.drawing?.id);
  
  const sheetCount = isMock ? set.sheets : (status?.sheet_count ?? 0);
  const blockCount = isMock ? 0 : (status?.block_count ?? 0);
  const processingStatus = isMock ? set.status : (status?.status || 'pending');
  
  const getStatusBadge = () => {
    switch (processingStatus) {
      case 'completed':
        return { variant: 'secondary' as const, text: 'Complete' };
      case 'processing':
        return { variant: 'outline' as const, text: 'Processing' };
      case 'failed':
        return { variant: 'destructive' as const, text: 'Failed' };
      default:
        return { variant: 'outline' as const, text: 'Pending' };
    }
  };
  
  const statusBadge = getStatusBadge();
  
  const handleClick = () => {
    if (!isMock && projectId) {
      // Navigate to sheets tab filtered by this drawing, or expand inline
      window.location.hash = `sheets-${set.id}`;
    }
  };
  
  return (
    <Card 
      className="cursor-pointer hover:border-primary/50 transition-all group"
      onClick={handleClick}
    >
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
            {statusLoading || processingStatus === 'processing' ? (
              <Loader2 className="w-5 h-5 text-primary animate-spin" />
            ) : (
              <FolderOpen className="w-5 h-5 text-primary" />
            )}
          </div>
          <Badge variant={statusBadge.variant} className="text-[10px]">
            {statusBadge.text}
          </Badge>
        </div>
        <CardTitle className="text-base mt-2">{set.name}</CardTitle>
        <CardDescription className="flex items-center gap-1 text-xs">
          <Calendar className="w-3 h-3" /> {set.date}
        </CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="flex items-center justify-between text-sm">
          <span className="text-muted-foreground">
            {sheetCount} {sheetCount === 1 ? 'sheet' : 'sheets'}
            {!isMock && blockCount > 0 && ` • ${blockCount} blocks`}
          </span>
          <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
        </div>
        <div className="flex flex-wrap gap-1 mt-2">
          {set.disciplines.slice(0, 2).map((d: string) => (
            <Badge key={d} variant="outline" className="text-[9px] h-4 px-1">{d}</Badge>
          ))}
          {set.disciplines.length > 2 && (
            <Badge variant="outline" className="text-[9px] h-4 px-1">+{set.disciplines.length - 2}</Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// Component for drawing set row in list view
function DrawingSetRow({ set, projectId, onViewSheets }: { set: any; projectId?: string; onViewSheets?: (drawingId: string) => void }) {
  const isMock = !set.drawing;
  const { data: status, isLoading: statusLoading } = useDrawingStatus(isMock ? undefined : set.drawing?.id);
  
  const sheetCount = isMock ? set.sheets : (status?.sheet_count ?? 0);
  const blockCount = isMock ? 0 : (status?.block_count ?? 0);
  const processingStatus = isMock ? set.status : (status?.status || 'pending');
  
  const getStatusBadge = () => {
    switch (processingStatus) {
      case 'completed':
        return { variant: 'secondary' as const, text: 'Complete' };
      case 'processing':
        return { variant: 'outline' as const, text: 'Processing' };
      case 'failed':
        return { variant: 'destructive' as const, text: 'Failed' };
      default:
        return { variant: 'outline' as const, text: 'Pending' };
    }
  };
  
  const statusBadge = getStatusBadge();
  
  const handleClick = () => {
    if (!isMock && projectId) {
      window.location.hash = `sheets-${set.id}`;
    }
  };
  
  return (
    <div 
      className="p-4 flex items-center justify-between hover:bg-muted/30 cursor-pointer transition-colors"
      onClick={handleClick}
    >
      <div className="flex items-center gap-4">
        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
          {statusLoading || processingStatus === 'processing' ? (
            <Loader2 className="w-5 h-5 text-primary animate-spin" />
          ) : (
            <FolderOpen className="w-5 h-5 text-primary" />
          )}
        </div>
        <div>
          <p className="font-medium">{set.name}</p>
          <p className="text-sm text-muted-foreground">
            {sheetCount} {sheetCount === 1 ? 'sheet' : 'sheets'}
            {!isMock && blockCount > 0 && ` • ${blockCount} blocks`}
            {` • ${set.date}`}
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <div className="flex gap-1">
          {set.disciplines.slice(0, 3).map((d: string) => (
            <Badge key={d} variant="outline" className="text-[10px]">{d}</Badge>
          ))}
        </div>
        <Badge variant={statusBadge.variant}>
          {statusBadge.text}
        </Badge>
        <DropdownMenu>
          <DropdownMenuTrigger asChild onClick={(e) => e.stopPropagation()}>
            <Button variant="ghost" size="icon" className="h-8 w-8">
              <MoreVertical className="w-4 h-4" />
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuItem 
              onClick={(e) => {
                e.stopPropagation();
                if (!isMock && set.drawing?.id && onViewSheets) {
                  onViewSheets(set.drawing.id);
                }
              }}
            >
              <Eye className="w-4 h-4 mr-2" /> View Sheets
            </DropdownMenuItem>
            <DropdownMenuItem><Download className="w-4 h-4 mr-2" /> Download All</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </div>
  );
}
