import DashboardLayout from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Link } from "wouter";
import { Plus, Clock, ArrowRight, Building2, AlertTriangle, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

export default function ProjectList() {
  // Fetch real projects from API
  const { data: projects, isLoading } = useQuery({
    queryKey: ['projects'],
    queryFn: () => api.projects.list(),
  });

  // Format time ago
  const timeAgo = (dateString: string) => {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffHrs < 1) return 'Just now';
    if (diffHrs < 24) return `${diffHrs} hour${diffHrs > 1 ? 's' : ''} ago`;
    if (diffDays < 30) return `${diffDays} day${diffDays > 1 ? 's' : ''} ago`;
    return `${Math.floor(diffDays / 30)} month${Math.floor(diffDays / 30) > 1 ? 's' : ''} ago`;
  };

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="flex items-center justify-center h-96">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </DashboardLayout>
    );
  }

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
          {projects && projects.map((project) => (
            <Link key={project.id} href={`/project/${project.id}`}>
              <Card className="hover:shadow-md transition-shadow cursor-pointer border-border group">
                <CardHeader className="pb-3">
                  <div className="flex justify-between items-start">
                    <Badge variant="default" className="mb-2">
                      Active
                    </Badge>
                    <div className="p-2 bg-muted rounded-full group-hover:bg-primary/10 group-hover:text-primary transition-colors">
                      <ArrowRight className="w-4 h-4 -rotate-45" />
                    </div>
                  </div>
                  <CardTitle className="leading-tight">{project.name}</CardTitle>
                  <CardDescription className="flex items-center gap-1">
                    <Building2 className="w-3 h-3" /> {project.address || 'No address'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 gap-4 pt-4 border-t border-border">
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Project Type</p>
                      <span className="text-sm font-medium capitalize">{project.project_type || '—'}</span>
                    </div>
                    <div>
                      <p className="text-xs text-muted-foreground mb-1">Phase</p>
                      <span className="text-sm font-medium capitalize">{project.phase || '—'}</span>
                    </div>
                  </div>
                  <div className="mt-4 flex items-center gap-2 text-xs text-muted-foreground bg-muted/30 p-2 rounded">
                    <Clock className="w-3 h-3" />
                    Created {timeAgo(project.created_at)}
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
