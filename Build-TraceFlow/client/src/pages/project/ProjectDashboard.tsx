import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Link } from "wouter";
import { ArrowUpRight, Calendar, DollarSign, FileDiff, Layers, MoreHorizontal, Plus, Upload, FileText } from "lucide-react";
import { Badge } from "@/components/ui/badge";

export default function ProjectDashboard() {
  return (
    <DashboardLayout>
      <div className="p-8 max-w-7xl mx-auto space-y-8">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-3 mb-1">
              <h1 className="text-3xl font-bold font-display tracking-tight">Memorial Hospital Expansion</h1>
              <Badge variant="outline" className="text-xs">Active</Badge>
            </div>
            <p className="text-muted-foreground">Healthcare • Boston, MA • GC: BuildCorps</p>
          </div>
          <div className="flex gap-3">
             <Button variant="outline">Project Settings</Button>
             <Link href="/project/123/new-overlay">
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
            value="+$124,500" 
            trend="+12% from last week" 
            trendUp={true}
            icon={<DollarSign className="w-4 h-4 text-muted-foreground" />} 
          />
          <StatCard 
            title="Schedule Drift" 
            value="4 Days" 
            trend="+2 days vs baseline" 
            trendUp={false}
            icon={<Calendar className="w-4 h-4 text-muted-foreground" />} 
          />
          <StatCard 
            title="Active Changes" 
            value="14" 
            trend="5 awaiting review" 
            icon={<FileDiff className="w-4 h-4 text-muted-foreground" />} 
          />
          <StatCard 
            title="Drawing Sets" 
            value="8" 
            trend="Latest: Bulletin 04" 
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
               {[
                 { title: "Bulletin 04 vs IFC", date: "Today, 10:23 AM", user: "Alex Morgan", changes: 14, sheets: 18, status: "Review Needed" },
                 { title: "RFI 102 Update", date: "Yesterday, 4:15 PM", user: "Sarah Chen", changes: 3, sheets: 5, status: "Completed" },
                 { title: "Plumbing Shop Drawings", date: "Jan 05, 2024", user: "Mike Ross", changes: 28, sheets: 42, status: "Completed" },
               ].map((item, i) => (
                 <Link key={i} href="/project/123/overlay">
                   <Card className="group hover:border-primary/50 transition-colors cursor-pointer">
                     <CardContent className="p-4 flex items-center justify-between">
                       <div className="flex items-center gap-4">
                         <div className="w-10 h-10 rounded-lg bg-primary/5 text-primary flex items-center justify-center">
                           <FileDiff className="w-5 h-5" />
                         </div>
                         <div>
                           <h3 className="font-semibold group-hover:text-primary transition-colors">{item.title}</h3>
                           <p className="text-xs text-muted-foreground">Run by {item.user} • {item.date}</p>
                         </div>
                       </div>
                       <div className="flex items-center gap-6">
                          <div className="text-right hidden sm:block">
                            <p className="text-sm font-medium">{item.changes} Changes</p>
                            <p className="text-xs text-muted-foreground">{item.sheets} Sheets</p>
                          </div>
                          <Badge variant={item.status === "Review Needed" ? "destructive" : "secondary"}>
                            {item.status}
                          </Badge>
                          <MoreHorizontal className="w-4 h-4 text-muted-foreground" />
                       </div>
                     </CardContent>
                   </Card>
                 </Link>
               ))}
            </div>

            {/* Drawing Sets Section */}
            <div className="pt-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-xl font-bold font-display">Drawing Sets</h2>
                <Button variant="outline" size="sm">
                  <Upload className="w-4 h-4 mr-2" /> Upload New
                </Button>
              </div>
              
              <div className="grid md:grid-cols-2 gap-4">
                {[
                  { name: "Bulletin 04", date: "Feb 28, 2024", sheets: 18, source: "Uploaded" },
                  { name: "Bulletin 03", date: "Feb 15, 2024", sheets: 15, source: "Procore" },
                  { name: "Bulletin 02", date: "Feb 01, 2024", sheets: 8, source: "Uploaded" },
                  { name: "IFC Set", date: "Jan 12, 2024", sheets: 142, source: "Autodesk CC" },
                ].map((set, i) => (
                  <Card key={i} className="hover:border-primary/30 transition-colors cursor-pointer">
                    <CardContent className="p-4 flex items-center gap-4">
                      <div className="w-10 h-10 rounded-lg bg-muted flex items-center justify-center">
                        <FileText className="w-5 h-5 text-muted-foreground" />
                      </div>
                      <div className="flex-1">
                        <p className="font-medium">{set.name}</p>
                        <p className="text-xs text-muted-foreground">{set.sheets} sheets • {set.date}</p>
                      </div>
                      <Badge variant="outline" className="text-xs">{set.source}</Badge>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>
          </div>

          {/* Right Column - Timeline */}
          <div className="space-y-6">
            <h2 className="text-xl font-bold font-display">Drawing Timeline</h2>
            <Card>
              <CardContent className="p-6">
                <div className="space-y-8 relative before:absolute before:left-[15px] before:top-2 before:bottom-2 before:w-[2px] before:bg-border">
                  {[
                    { label: "Bulletin 04", date: "Feb 28", active: true },
                    { label: "Bulletin 03", date: "Feb 15", active: false },
                    { label: "Addendum 02", date: "Jan 30", active: false },
                    { label: "IFC Set", date: "Jan 12", active: false },
                  ].map((item, i) => (
                    <div key={i} className="relative pl-8">
                       <div className={`absolute left-0 top-1 w-8 h-8 rounded-full border-4 border-background flex items-center justify-center z-10 ${item.active ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
                         <div className="w-2 h-2 rounded-full bg-current" />
                       </div>
                       <div>
                         <p className={`font-semibold ${item.active ? "text-foreground" : "text-muted-foreground"}`}>{item.label}</p>
                         <p className="text-xs text-muted-foreground">{item.date}</p>
                       </div>
                    </div>
                  ))}
                </div>
                <Button variant="outline" className="w-full mt-8">View Full Timeline</Button>
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
