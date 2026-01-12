import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Link, useParams } from "wouter";
import { ArrowUpRight, Calendar, DollarSign, FileDiff, Layers, MoreHorizontal, Plus, Upload, FileText, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

export default function ProjectDashboard() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;

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
             <Button variant="outline">Project Settings</Button>
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
                 comparisons.slice(0, 5).map((comparison) => (
                   <Link key={comparison.id} href={`/project/${projectId}/overlay/${comparison.id}`}>
                     <Card className="group hover:border-primary/50 transition-colors cursor-pointer">
                       <CardContent className="p-4 flex items-center justify-between">
                         <div className="flex items-center gap-4">
                           <div className="w-10 h-10 rounded-lg bg-primary/5 text-primary flex items-center justify-center">
                             <FileDiff className="w-5 h-5" />
                           </div>
                           <div>
                             <h3 className="font-semibold group-hover:text-primary transition-colors">
                               Comparison #{comparison.id.slice(0, 8)}
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
                  drawings.slice(0, 4).map((drawing) => (
                    <Card key={drawing.id} className="hover:border-primary/30 transition-colors cursor-pointer">
                      <CardContent className="p-4 flex items-center gap-4">
                        <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
                          <FileText className="w-5 h-5 text-muted-foreground" />
                        </div>
                        <div className="flex-1">
                          <p className="font-medium">{drawing.name || drawing.filename}</p>
                          <p className="text-xs text-muted-foreground">
                            {drawing.sheet_count} sheets • {new Date(drawing.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <Badge variant="outline" className="text-xs capitalize">{drawing.status || 'Uploaded'}</Badge>
                      </CardContent>
                    </Card>
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
                      {drawings.slice(0, 4).map((drawing, i) => (
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
                <Link href="/project/123/new-overlay">
                  <Button variant="outline" className="w-full justify-start gap-2">
                    <FileDiff className="w-4 h-4" /> Start New Comparison
                  </Button>
                </Link>
                <Button variant="outline" className="w-full justify-start gap-2">
                  <Upload className="w-4 h-4" /> Upload Drawing Set
                </Button>
                <Link href="/project/123/cost">
                  <Button variant="outline" className="w-full justify-start gap-2">
                    <DollarSign className="w-4 h-4" /> View Cost Report
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>
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
