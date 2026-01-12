import { Link, useLocation } from "wouter";
import { Button } from "@/components/ui/button";
import { 
  LayoutDashboard, 
  Layers, 
  FileDiff, 
  BarChart3, 
  Settings, 
  Bell, 
  Search,
  ChevronDown,
  LogOut,
  FolderOpen,
  User,
  CreditCard,
  Users,
  Coins,
  PanelLeftClose,
  PanelLeftOpen,
  ChevronRight,
  FileText
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import logo from "@assets/BuildTrace_Logo_1767832159404.jpg";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";

interface DashboardLayoutProps {
  children: React.ReactNode;
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const [location, setLocation] = useLocation();
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [comparisonsExpanded, setComparisonsExpanded] = useState(true);
  const [analysisExpanded, setAnalysisExpanded] = useState(true);

  const isProjectRoute = location.includes("/project/");
  const projectId = isProjectRoute ? location.split("/")[2] : null;

  // Fetch actual project data
  const { data: project } = useQuery({
    queryKey: ['project', projectId],
    queryFn: () => api.projects.get(projectId!),
    enabled: !!projectId,
  });

  // Fetch comparisons for this project
  const { data: comparisonsData } = useQuery({
    queryKey: ['project', projectId, 'comparisons'],
    queryFn: () => api.comparisons.listByProject(projectId!),
    enabled: !!projectId,
  });

  const projectName = project?.name || "Loading...";
  const comparisons = comparisonsData?.slice(0, 5).map(c => ({
    id: c.id,
    name: `Comparison #${c.id.slice(0, 6)}`,
    date: new Date(c.created_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }),
    isProcessed: c.status === 'completed',
  })) || [];

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside className={`${sidebarCollapsed ? 'w-16' : 'w-64'} border-r border-border bg-sidebar sticky top-0 h-screen flex flex-col transition-all duration-300`}>
        <div className={`p-4 border-b border-sidebar-border flex items-center ${sidebarCollapsed ? 'justify-center' : 'justify-between'}`}>
          <Link href="/">
            <div className="flex items-center gap-2 cursor-pointer">
              <img src={logo} alt="BuildTrace" className="w-8 h-8 rounded-md" />
              {!sidebarCollapsed && (
                <span className="text-lg font-bold tracking-tight font-display text-sidebar-foreground">BuildTrace</span>
              )}
            </div>
          </Link>
          {!sidebarCollapsed && (
            <Button variant="ghost" size="icon" className="h-7 w-7" onClick={() => setSidebarCollapsed(true)}>
              <PanelLeftClose className="w-4 h-4" />
            </Button>
          )}
        </div>

        {sidebarCollapsed ? (
          <div className="flex-1 py-4 flex flex-col items-center gap-2">
            <Button variant="ghost" size="icon" className="h-10 w-10" onClick={() => setSidebarCollapsed(false)}>
              <PanelLeftOpen className="w-4 h-4" />
            </Button>
            <div className="w-8 h-px bg-border my-2" />
            <Link href="/dashboard">
              <Button variant={location === "/dashboard" ? "secondary" : "ghost"} size="icon" className="h-10 w-10">
                <FolderOpen className="w-4 h-4" />
              </Button>
            </Link>
            {isProjectRoute && (
              <>
                <div className="w-8 h-px bg-border my-2" />
                <Link href={`/project/${projectId}`}>
                  <Button variant={location === `/project/${projectId}` ? "secondary" : "ghost"} size="icon" className="h-10 w-10">
                    <LayoutDashboard className="w-4 h-4" />
                  </Button>
                </Link>
                <Link href={`/project/${projectId}/overlay`}>
                  <Button variant={location.includes('/overlay') ? "secondary" : "ghost"} size="icon" className="h-10 w-10">
                    <FileDiff className="w-4 h-4" />
                  </Button>
                </Link>
                <Link href={`/project/${projectId}/cost`}>
                  <Button variant={location.includes('/cost') ? "secondary" : "ghost"} size="icon" className="h-10 w-10">
                    <BarChart3 className="w-4 h-4" />
                  </Button>
                </Link>
                <Link href={`/project/${projectId}/drawings`}>
                  <Button variant={location.includes('/drawings') ? "secondary" : "ghost"} size="icon" className="h-10 w-10">
                    <Layers className="w-4 h-4" />
                  </Button>
                </Link>
              </>
            )}
          </div>
        ) : (
          <div className="flex-1 py-4 px-3 space-y-1 overflow-y-auto">
            <div className="mb-4">
              <h3 className="px-2 text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wider">Workspace</h3>
              <SidebarItem href="/dashboard" icon={<FolderOpen className="w-4 h-4" />} active={location === "/dashboard"}>
                All Projects
              </SidebarItem>
            </div>

            {isProjectRoute && (
              <div className="mb-4 animate-in slide-in-from-left-2 duration-300">
                {/* Project Header */}
                <div className="px-2 mb-3 py-2 bg-muted/30 rounded-lg">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-1">Current Project</p>
                  <p className="text-sm font-medium truncate">{projectName}</p>
                </div>

                <div className="space-y-1">
                  <SidebarItem href={`/project/${projectId}`} icon={<LayoutDashboard className="w-4 h-4" />} active={location === `/project/${projectId}`}>
                    Overview
                  </SidebarItem>
                  
                  {/* Comparisons Section */}
                  <Collapsible open={comparisonsExpanded} onOpenChange={setComparisonsExpanded}>
                    <CollapsibleTrigger asChild>
                      <div className="flex items-center justify-between px-3 py-2 rounded-md text-sm font-medium text-muted-foreground hover:bg-sidebar-accent/50 cursor-pointer">
                        <div className="flex items-center gap-3">
                          <FileDiff className="w-4 h-4" />
                          <span>Comparisons</span>
                        </div>
                        <ChevronRight className={`w-3 h-3 transition-transform ${comparisonsExpanded ? 'rotate-90' : ''}`} />
                      </div>
                    </CollapsibleTrigger>
                    <CollapsibleContent className="pl-6 space-y-0.5 mt-1">
                      <Link href={`/project/${projectId}/new-overlay`}>
                        <div className="px-3 py-1.5 text-xs text-primary hover:bg-primary/5 rounded-md cursor-pointer flex items-center gap-2">
                          <span>+ New Comparison</span>
                        </div>
                      </Link>
                      {comparisons.map((c) => (
                        <Link key={c.id} href={`/project/${projectId}/overlay`}>
                          <div className={`px-3 py-1.5 text-xs rounded-md cursor-pointer flex items-center justify-between hover:bg-sidebar-accent/50 ${location.includes('/overlay') ? 'bg-sidebar-accent text-foreground' : 'text-muted-foreground'}`}>
                            <span className="truncate">{c.name}</span>
                            <span className="text-[10px] text-muted-foreground/60">{c.date}</span>
                          </div>
                        </Link>
                      ))}
                    </CollapsibleContent>
                  </Collapsible>

                  {/* Cost & Schedule Section */}
                  <SidebarItem href={`/project/${projectId}/cost`} icon={<BarChart3 className="w-4 h-4" />} active={location.includes('/cost')}>
                    Cost & Schedule
                  </SidebarItem>

                  <SidebarItem href={`/project/${projectId}/drawings`} icon={<Layers className="w-4 h-4" />} active={location.includes('/drawings')}>
                    Drawings
                  </SidebarItem>
                </div>
              </div>
            )}
            
            <div className="pt-4">
              <h3 className="px-2 text-xs font-semibold text-muted-foreground mb-2 uppercase tracking-wider">Account</h3>
              <SidebarItem href="/settings" icon={<Settings className="w-4 h-4" />} active={location === "/settings"}>
                Settings
              </SidebarItem>
              <SidebarItem href="/credits" icon={<Coins className="w-4 h-4" />} active={location === "/credits"}>
                Credits
              </SidebarItem>
            </div>
          </div>
        )}

        {!sidebarCollapsed && (
          <div className="p-4 border-t border-sidebar-border">
             <div className="bg-sidebar-accent/50 rounded-lg p-3">
                <p className="text-xs font-medium text-foreground">Pro Plan</p>
                <div className="w-full bg-sidebar-border h-1.5 rounded-full mt-2 mb-1">
                  <div className="bg-sidebar-primary h-1.5 rounded-full w-[70%]"></div>
                </div>
                <p className="text-[10px] text-muted-foreground">7/10 Projects used</p>
             </div>
          </div>
        )}
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col min-w-0">
        {/* Topbar */}
        <header className="h-16 border-b border-border bg-background flex items-center justify-between px-6 sticky top-0 z-40">
          <div className="flex items-center gap-4 flex-1">
            {isProjectRoute ? (
               <div className="flex items-center gap-2">
                 <Link href="/dashboard">
                   <span className="text-muted-foreground hover:text-foreground cursor-pointer">Projects /</span>
                 </Link>
                 <Button variant="ghost" className="font-semibold px-2 -ml-2 h-8 text-foreground">
                   {projectName}
                 </Button>
               </div>
            ) : (
              <div className="relative w-96 hidden md:block">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input placeholder="Search projects, sheets, or changes..." className="pl-9 bg-muted/40 border-transparent focus-visible:bg-background focus-visible:border-primary" />
              </div>
            )}
          </div>

          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" className="relative text-muted-foreground hover:text-foreground">
              <Bell className="w-5 h-5" />
              <span className="absolute top-3 right-3 w-2 h-2 bg-destructive rounded-full border-2 border-background"></span>
            </Button>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="pl-2 pr-0 gap-2 hover:bg-transparent">
                   <div className="text-right hidden md:block">
                     <p className="text-sm font-medium leading-none">Alex Morgan</p>
                     <p className="text-xs text-muted-foreground mt-1">Project Manager</p>
                   </div>
                   <Avatar className="h-8 w-8 border border-border">
                    <AvatarImage src="https://github.com/shadcn.png" />
                    <AvatarFallback>AM</AvatarFallback>
                  </Avatar>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>My Account</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={() => setLocation("/profile")}>
                  <User className="mr-2 w-4 h-4" />
                  View Profile
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setLocation("/credits")}>
                  <CreditCard className="mr-2 w-4 h-4" />
                  Account & Billing
                </DropdownMenuItem>
                <DropdownMenuItem onClick={() => setLocation("/profile")}>
                  <Users className="mr-2 w-4 h-4" />
                  Organization / Team
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem className="text-destructive focus:text-destructive" onClick={() => setLocation("/")}>
                  <LogOut className="mr-2 w-4 h-4" />
                  Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        {/* Page Content */}
        <div className="flex-1 overflow-auto">
          {children}
        </div>
      </main>
    </div>
  );
}

function SidebarItem({ href, icon, children, active }: { href: string, icon: React.ReactNode, children: React.ReactNode, active: boolean }) {
  return (
    <Link href={href}>
      <div className={`
        flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors cursor-pointer
        ${active 
          ? 'bg-sidebar-accent text-sidebar-foreground shadow-sm border border-sidebar-border' 
          : 'text-muted-foreground hover:bg-sidebar-accent/50 hover:text-foreground'}
      `}>
        <span className={active ? "text-sidebar-primary" : "text-muted-foreground group-hover:text-foreground"}>
          {icon}
        </span>
        {children}
      </div>
    </Link>
  );
}
