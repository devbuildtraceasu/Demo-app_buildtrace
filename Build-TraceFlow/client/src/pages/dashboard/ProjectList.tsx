import DashboardLayout from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Link } from "wouter";
import { Plus, Clock, ArrowRight, Building2, AlertTriangle, FileText } from "lucide-react";

export default function ProjectList() {
  const projects = [
    {
      id: "123",
      name: "Memorial Hospital Expansion",
      location: "Boston, MA",
      status: "Active",
      lastActivity: "2 hours ago",
      changes: 14,
      costImpact: "+$124k"
    },
    {
      id: "124",
      name: "Downtown Lab Complex",
      location: "Cambridge, MA",
      status: "Active",
      lastActivity: "1 day ago",
      changes: 3,
      costImpact: "+$12k"
    },
    {
      id: "125",
      name: "Seaport Multifamily Tower",
      location: "Boston, MA",
      status: "Archived",
      lastActivity: "2 months ago",
      changes: 0,
      costImpact: "$0"
    }
  ];

  return (
    <DashboardLayout>
      <div className="p-8 max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-8">
          <div>
            <h1 className="text-3xl font-bold font-display tracking-tight">Projects</h1>
            <p className="text-muted-foreground">Manage your active construction sites and drawing sets.</p>
          </div>
          <Link href="/onboarding">
            <Button>
              <Plus className="mr-2 w-4 h-4" /> New Project
            </Button>
          </Link>
        </div>

        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((project) => (
            <Link key={project.id} href={`/project/${project.id}`}>
              <Card className="hover:shadow-md transition-shadow cursor-pointer border-border group">
                <CardHeader className="pb-3">
                  <div className="flex justify-between items-start">
                    <Badge variant={project.status === "Active" ? "default" : "secondary"} className="mb-2">
                      {project.status}
                    </Badge>
                    <div className="p-2 bg-muted rounded-full group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                      <ArrowRight className="w-4 h-4 -rotate-45" />
                    </div>
                  </div>
                  <CardTitle className="leading-tight">{project.name}</CardTitle>
                  <CardDescription className="flex items-center gap-1">
                    <Building2 className="w-3 h-3" /> {project.location}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border">
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Unresolved Changes</p>
                      <div className="flex items-center gap-2">
                         <span className="text-xl font-bold font-display">{project.changes}</span>
                         {project.changes > 0 && <AlertTriangle className="w-4 h-4 text-amber-500" />}
                      </div>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Est. Cost Impact</p>
                      <span className="text-xl font-bold font-display text-muted-foreground">{project.costImpact}</span>
                    </div>
                  </div>
                  <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground bg-muted/30 p-2 rounded">
                    <Clock className="w-3 h-3" />
                    Last activity {project.lastActivity}
                  </div>
                </CardContent>
              </Card>
            </Link>
          ))}
          
          <Link href="/onboarding">
            <Card className="border-border border-dashed hover:border-primary/50 hover:bg-muted/10 transition-colors cursor-pointer flex flex-col items-center justify-center h-full min-h-[250px]">
              <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-4">
                <Plus className="w-6 h-6 text-muted-foreground" />
              </div>
              <p className="font-medium">Create New Project</p>
            </Card>
          </Link>
        </div>
      </div>
    </DashboardLayout>
  );
}
