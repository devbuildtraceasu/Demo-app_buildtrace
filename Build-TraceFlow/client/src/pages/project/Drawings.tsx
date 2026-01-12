import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
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
  LinkIcon
} from "lucide-react";
import { useState } from "react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export default function Drawings() {
  const [viewMode, setViewMode] = useState<"grid" | "list">("list");
  const [hasDrawings, setHasDrawings] = useState(true);

  const drawingSets = [
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

  const sheets = [
    { id: "A-101", name: "First Floor Plan", discipline: "Architectural", set: "Bulletin 03", date: "Feb 15" },
    { id: "A-102", name: "Second Floor Plan", discipline: "Architectural", set: "Bulletin 03", date: "Feb 15" },
    { id: "A-201", name: "Building Elevations", discipline: "Architectural", set: "Bulletin 03", date: "Feb 15" },
    { id: "S-101", name: "Foundation Plan", discipline: "Structural", set: "IFC Set", date: "Jan 12" },
    { id: "S-102", name: "Framing Plan Level 2", discipline: "Structural", set: "Bulletin 01", date: "Jan 20" },
    { id: "M-101", name: "HVAC Floor Plan L1", discipline: "Mechanical", set: "Bulletin 02", date: "Feb 01" },
    { id: "E-101", name: "Electrical Floor Plan L1", discipline: "Electrical", set: "Bulletin 03", date: "Feb 15" },
    { id: "P-101", name: "Plumbing Floor Plan L1", discipline: "Plumbing", set: "Bulletin 03", date: "Feb 15" },
  ];

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
              <Card className="cursor-pointer hover:border-primary/50 transition-all group">
                <CardContent className="p-6 text-center">
                  <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mx-auto mb-3 group-hover:bg-primary/20 transition-colors">
                    <Upload className="w-6 h-6 text-primary" />
                  </div>
                  <p className="font-medium text-sm mb-1">Upload Files</p>
                  <p className="text-xs text-muted-foreground">PDF, DWG, DXF</p>
                </CardContent>
              </Card>
              
              <Card className="cursor-pointer hover:border-primary/50 transition-all group">
                <CardContent className="p-6 text-center">
                  <div className="w-12 h-12 rounded-lg bg-orange-100 flex items-center justify-center mx-auto mb-3 group-hover:bg-orange-200 transition-colors">
                    <CloudUpload className="w-6 h-6 text-orange-600" />
                  </div>
                  <p className="font-medium text-sm mb-1">Connect Procore</p>
                  <p className="text-xs text-muted-foreground">Import from project</p>
                </CardContent>
              </Card>
              
              <Card className="cursor-pointer hover:border-primary/50 transition-all group">
                <CardContent className="p-6 text-center">
                  <div className="w-12 h-12 rounded-lg bg-blue-100 flex items-center justify-center mx-auto mb-3 group-hover:bg-blue-200 transition-colors">
                    <LinkIcon className="w-6 h-6 text-blue-600" />
                  </div>
                  <p className="font-medium text-sm mb-1">Connect ACC</p>
                  <p className="text-xs text-muted-foreground">Autodesk Cloud</p>
                </CardContent>
              </Card>
            </div>

            <Button variant="link" className="mt-6" onClick={() => setHasDrawings(true)}>
              Show demo drawings →
            </Button>
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
                  <Card key={set.id} className="cursor-pointer hover:border-primary/50 transition-all group">
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                          <FolderOpen className="w-5 h-5 text-primary" />
                        </div>
                        <Badge variant={set.status === "Complete" ? "secondary" : "outline"} className="text-[10px]">
                          {set.status}
                        </Badge>
                      </div>
                      <CardTitle className="text-base mt-2">{set.name}</CardTitle>
                      <CardDescription className="flex items-center gap-1 text-xs">
                        <Calendar className="w-3 h-3" /> {set.date}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="pt-0">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-muted-foreground">{set.sheets} sheets</span>
                        <ChevronRight className="w-4 h-4 text-muted-foreground group-hover:text-primary transition-colors" />
                      </div>
                      <div className="flex flex-wrap gap-1 mt-2">
                        {set.disciplines.slice(0, 2).map((d) => (
                          <Badge key={d} variant="outline" className="text-[9px] h-4 px-1">{d}</Badge>
                        ))}
                        {set.disciplines.length > 2 && (
                          <Badge variant="outline" className="text-[9px] h-4 px-1">+{set.disciplines.length - 2}</Badge>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            ) : (
              <Card>
                <div className="divide-y divide-border">
                  {drawingSets.map((set) => (
                    <div key={set.id} className="p-4 flex items-center justify-between hover:bg-muted/30 cursor-pointer transition-colors">
                      <div className="flex items-center gap-4">
                        <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                          <FolderOpen className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <p className="font-medium">{set.name}</p>
                          <p className="text-sm text-muted-foreground">{set.sheets} sheets • {set.date}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <div className="flex gap-1">
                          {set.disciplines.slice(0, 3).map((d) => (
                            <Badge key={d} variant="outline" className="text-[10px]">{d}</Badge>
                          ))}
                        </div>
                        <Badge variant={set.status === "Complete" ? "secondary" : "outline"}>
                          {set.status}
                        </Badge>
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <MoreVertical className="w-4 h-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end">
                            <DropdownMenuItem><Eye className="w-4 h-4 mr-2" /> View Sheets</DropdownMenuItem>
                            <DropdownMenuItem><Download className="w-4 h-4 mr-2" /> Download All</DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </TabsContent>

          <TabsContent value="sheets">
            <Card>
              <div className="divide-y divide-border">
                {sheets.map((sheet) => (
                  <div key={sheet.id} className="p-4 flex items-center justify-between hover:bg-muted/30 cursor-pointer transition-colors">
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
                      <Button variant="ghost" size="sm" className="h-7 gap-1">
                        <Eye className="w-3 h-3" /> View
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
