import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { 
  Search, 
  ShieldAlert, 
  Building, 
  Users, 
  Layers, 
  FolderOpen, 
  Trash2, 
  MoreHorizontal,
  AlertTriangle,
  Calendar,
  FileText
} from "lucide-react";
import { Link } from "wouter";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { useState } from "react";

export default function GodMode() {
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const users = [
    { name: "Alex Morgan", email: "alex@buildcorps.com", org: "BuildCorps Construction", role: "Admin", lastLogin: "2 hours ago", projects: 7, status: "Active" },
    { name: "Sarah Chen", email: "sarah@buildcorps.com", org: "BuildCorps Construction", role: "Member", lastLogin: "1 day ago", projects: 4, status: "Active" },
    { name: "Mike Ross", email: "mike@globalstruct.com", org: "Global Structures Inc.", role: "Admin", lastLogin: "3 hours ago", projects: 12, status: "Active" },
    { name: "Jennifer Wu", email: "jen@metrobuilders.com", org: "Metro Builders LLC", role: "Member", lastLogin: "2 weeks ago", projects: 2, status: "Suspended" },
    { name: "David Kim", email: "david@nextgen.com", org: "NextGen Architects", role: "Viewer", lastLogin: "5 days ago", projects: 1, status: "Active" },
  ];

  const projects = [
    { name: "Memorial Hospital Expansion", owner: "Alex Morgan", org: "BuildCorps", sets: 8, lastComparison: "Today, 10:23 AM", sheets: 142 },
    { name: "Downtown Lab Complex", owner: "Sarah Chen", org: "BuildCorps", sets: 5, lastComparison: "Yesterday", sheets: 89 },
    { name: "City Hall Renovation", owner: "Mike Ross", org: "Global Structures", sets: 12, lastComparison: "Jan 10, 2024", sheets: 234 },
    { name: "Seaport Multifamily", owner: "Alex Morgan", org: "BuildCorps", sets: 3, lastComparison: "Dec 15, 2023", sheets: 67 },
  ];

  const drawingSets = [
    { name: "IFC Set - Jan 12", sheets: 142, uploaded: "Jan 12, 2024", size: "245 MB" },
    { name: "Bulletin 01", sheets: 12, uploaded: "Jan 20, 2024", size: "34 MB" },
    { name: "Bulletin 02", sheets: 8, uploaded: "Feb 01, 2024", size: "22 MB" },
    { name: "Bulletin 03", sheets: 15, uploaded: "Feb 15, 2024", size: "41 MB" },
    { name: "Bulletin 04", sheets: 18, uploaded: "Feb 28, 2024", size: "48 MB" },
  ];

  return (
    <div className="min-h-screen bg-slate-950 text-slate-50 font-sans">
      <header className="h-16 border-b border-slate-800 flex items-center px-6 justify-between bg-slate-900">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-6 h-6 text-red-500" />
          <span className="font-bold font-display text-lg tracking-tight">BuildTrace Admin Console</span>
          <Badge variant="outline" className="ml-2 border-red-900 text-red-400">Internal Only</Badge>
        </div>
        <Link href="/dashboard">
          <Button variant="ghost" className="text-slate-400 hover:text-white">Exit to App</Button>
        </Link>
      </header>

      <main className="p-8 max-w-7xl mx-auto space-y-8">
        {/* Stats */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
          <Card className="bg-slate-900 border-slate-800 text-slate-50">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Organizations</CardTitle>
              <Building className="w-4 h-4 text-slate-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">1,248</div>
              <p className="text-xs text-slate-500">+12 this week</p>
            </CardContent>
          </Card>
          <Card className="bg-slate-900 border-slate-800 text-slate-50">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Active Users</CardTitle>
              <Users className="w-4 h-4 text-slate-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">8,502</div>
              <p className="text-xs text-slate-500">+89 this week</p>
            </CardContent>
          </Card>
          <Card className="bg-slate-900 border-slate-800 text-slate-50">
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Total Projects</CardTitle>
              <FolderOpen className="w-4 h-4 text-slate-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">4,891</div>
              <p className="text-xs text-slate-500">+156 this week</p>
            </CardContent>
          </Card>
          <Card className="bg-slate-900 border-slate-800 text-slate-50">
             <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium text-slate-400">Sheets Processed</CardTitle>
              <Layers className="w-4 h-4 text-slate-500" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">142,893</div>
              <p className="text-xs text-slate-500">+3,241 this week</p>
            </CardContent>
          </Card>
        </div>

        <Tabs defaultValue="users" className="space-y-6">
          <TabsList className="bg-slate-900 border border-slate-800">
            <TabsTrigger value="users" className="data-[state=active]:bg-slate-800">User Management</TabsTrigger>
            <TabsTrigger value="activity" className="data-[state=active]:bg-slate-800">Activity / Uploads</TabsTrigger>
            <TabsTrigger value="assets" className="data-[state=active]:bg-slate-800">Drawing & Data</TabsTrigger>
          </TabsList>

          {/* User Management */}
          <TabsContent value="users" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">User Management</h2>
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <Input 
                  placeholder="Search users..." 
                  className="pl-9 bg-slate-900 border-slate-800 text-slate-50 focus-visible:ring-slate-700"
                />
              </div>
            </div>

            <div className="rounded-md border border-slate-800 overflow-hidden">
              <Table>
                <TableHeader className="bg-slate-900">
                  <TableRow className="border-slate-800 hover:bg-slate-900">
                    <TableHead className="text-slate-400">User</TableHead>
                    <TableHead className="text-slate-400">Organization</TableHead>
                    <TableHead className="text-slate-400">Role</TableHead>
                    <TableHead className="text-slate-400">Last Login</TableHead>
                    <TableHead className="text-slate-400">Projects</TableHead>
                    <TableHead className="text-slate-400">Status</TableHead>
                    <TableHead className="text-right text-slate-400">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody className="bg-slate-950">
                  {users.map((user, i) => (
                    <TableRow key={i} className="border-slate-800 hover:bg-slate-900">
                      <TableCell>
                        <div>
                          <p className="font-medium text-slate-200">{user.name}</p>
                          <p className="text-xs text-slate-500">{user.email}</p>
                        </div>
                      </TableCell>
                      <TableCell className="text-slate-400">{user.org}</TableCell>
                      <TableCell>
                        <Select defaultValue={user.role.toLowerCase()}>
                          <SelectTrigger className="w-[100px] h-8 bg-slate-900 border-slate-700 text-slate-300">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent className="bg-slate-900 border-slate-800">
                            <SelectItem value="admin">Admin</SelectItem>
                            <SelectItem value="member">Member</SelectItem>
                            <SelectItem value="viewer">Viewer</SelectItem>
                          </SelectContent>
                        </Select>
                      </TableCell>
                      <TableCell className="text-slate-400">{user.lastLogin}</TableCell>
                      <TableCell className="text-slate-400">{user.projects}</TableCell>
                      <TableCell>
                        <Badge variant="outline" className={user.status === "Active" ? "border-green-900 text-green-400" : "border-red-900 text-red-400"}>
                          {user.status}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <DropdownMenu>
                          <DropdownMenuTrigger asChild>
                            <Button variant="ghost" size="icon" className="h-8 w-8 text-slate-400 hover:text-white">
                              <MoreHorizontal className="w-4 h-4" />
                            </Button>
                          </DropdownMenuTrigger>
                          <DropdownMenuContent align="end" className="bg-slate-900 border-slate-800">
                            <DropdownMenuItem className="text-slate-300">View Details</DropdownMenuItem>
                            <DropdownMenuItem className="text-slate-300">Reset Password</DropdownMenuItem>
                            <DropdownMenuSeparator className="bg-slate-800" />
                            <DropdownMenuItem className={user.status === "Active" ? "text-amber-400" : "text-green-400"}>
                              {user.status === "Active" ? "Suspend User" : "Reactivate User"}
                            </DropdownMenuItem>
                          </DropdownMenuContent>
                        </DropdownMenu>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </TabsContent>

          {/* Activity / Uploads */}
          <TabsContent value="activity" className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-xl font-bold">Project Activity</h2>
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                <Input 
                  placeholder="Search projects..." 
                  className="pl-9 bg-slate-900 border-slate-800 text-slate-50"
                />
              </div>
            </div>

            <div className="rounded-md border border-slate-800 overflow-hidden">
              <Table>
                <TableHeader className="bg-slate-900">
                  <TableRow className="border-slate-800">
                    <TableHead className="text-slate-400">Project</TableHead>
                    <TableHead className="text-slate-400">Owner</TableHead>
                    <TableHead className="text-slate-400">Organization</TableHead>
                    <TableHead className="text-slate-400">Drawing Sets</TableHead>
                    <TableHead className="text-slate-400">Sheets</TableHead>
                    <TableHead className="text-slate-400">Last Comparison</TableHead>
                    <TableHead className="text-right text-slate-400">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody className="bg-slate-950">
                  {projects.map((project, i) => (
                    <TableRow key={i} className="border-slate-800 hover:bg-slate-900 cursor-pointer">
                      <TableCell className="font-medium text-slate-200">
                        <div className="flex items-center gap-2">
                          <FolderOpen className="w-4 h-4 text-slate-500" />
                          {project.name}
                        </div>
                      </TableCell>
                      <TableCell className="text-slate-400">{project.owner}</TableCell>
                      <TableCell className="text-slate-400">{project.org}</TableCell>
                      <TableCell className="text-slate-400">{project.sets}</TableCell>
                      <TableCell className="text-slate-400">{project.sheets}</TableCell>
                      <TableCell className="text-slate-400">
                        <div className="flex items-center gap-1">
                          <Calendar className="w-3 h-3" />
                          {project.lastComparison}
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button variant="ghost" size="sm" className="text-slate-400 hover:text-white">
                          Open
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          </TabsContent>

          {/* Drawing & Data Management */}
          <TabsContent value="assets" className="space-y-4">
            <Card className="bg-slate-900 border-slate-800">
              <CardHeader>
                <CardTitle className="text-slate-200">Project: Memorial Hospital Expansion</CardTitle>
                <CardDescription className="text-slate-500">Manage drawing sets and project data</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center justify-between">
                  <h3 className="font-semibold text-slate-300">Uploaded Drawing Sets</h3>
                  <AlertDialog>
                    <AlertDialogTrigger asChild>
                      <Button variant="destructive" size="sm" className="bg-red-900/50 hover:bg-red-900 text-red-400">
                        <Trash2 className="w-4 h-4 mr-2" /> Delete Entire Project
                      </Button>
                    </AlertDialogTrigger>
                    <AlertDialogContent className="bg-slate-900 border-slate-800">
                      <AlertDialogHeader>
                        <AlertDialogTitle className="text-slate-200 flex items-center gap-2">
                          <AlertTriangle className="w-5 h-5 text-red-500" />
                          Delete Project?
                        </AlertDialogTitle>
                        <AlertDialogDescription className="text-slate-400">
                          This will permanently delete "Memorial Hospital Expansion" and all associated drawing sets, comparisons, and data. This action cannot be undone.
                        </AlertDialogDescription>
                      </AlertDialogHeader>
                      <AlertDialogFooter>
                        <AlertDialogCancel className="bg-slate-800 border-slate-700 text-slate-300 hover:bg-slate-700">Cancel</AlertDialogCancel>
                        <AlertDialogAction className="bg-red-600 hover:bg-red-700">Delete Project</AlertDialogAction>
                      </AlertDialogFooter>
                    </AlertDialogContent>
                  </AlertDialog>
                </div>

                <div className="rounded-md border border-slate-800 overflow-hidden">
                  <Table>
                    <TableHeader className="bg-slate-800/50">
                      <TableRow className="border-slate-700">
                        <TableHead className="text-slate-400">Drawing Set</TableHead>
                        <TableHead className="text-slate-400">Sheets</TableHead>
                        <TableHead className="text-slate-400">Uploaded</TableHead>
                        <TableHead className="text-slate-400">Size</TableHead>
                        <TableHead className="text-right text-slate-400">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {drawingSets.map((set, i) => (
                        <TableRow key={i} className="border-slate-800 hover:bg-slate-800/30">
                          <TableCell className="text-slate-200">
                            <div className="flex items-center gap-2">
                              <FileText className="w-4 h-4 text-slate-500" />
                              {set.name}
                            </div>
                          </TableCell>
                          <TableCell className="text-slate-400">{set.sheets}</TableCell>
                          <TableCell className="text-slate-400">{set.uploaded}</TableCell>
                          <TableCell className="text-slate-400">{set.size}</TableCell>
                          <TableCell className="text-right">
                            <AlertDialog>
                              <AlertDialogTrigger asChild>
                                <Button variant="ghost" size="icon" className="h-8 w-8 text-red-400 hover:text-red-300 hover:bg-red-900/30">
                                  <Trash2 className="w-4 h-4" />
                                </Button>
                              </AlertDialogTrigger>
                              <AlertDialogContent className="bg-slate-900 border-slate-800">
                                <AlertDialogHeader>
                                  <AlertDialogTitle className="text-slate-200">Delete Drawing Set?</AlertDialogTitle>
                                  <AlertDialogDescription className="text-slate-400">
                                    This will permanently delete "{set.name}" and all associated comparison data. This action cannot be undone.
                                  </AlertDialogDescription>
                                </AlertDialogHeader>
                                <AlertDialogFooter>
                                  <AlertDialogCancel className="bg-slate-800 border-slate-700 text-slate-300">Cancel</AlertDialogCancel>
                                  <AlertDialogAction className="bg-red-600 hover:bg-red-700">Delete</AlertDialogAction>
                                </AlertDialogFooter>
                              </AlertDialogContent>
                            </AlertDialog>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}
