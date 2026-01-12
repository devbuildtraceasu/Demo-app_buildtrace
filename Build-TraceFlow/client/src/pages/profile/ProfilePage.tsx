import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { User, Mail, Phone, Building2, Shield, UserPlus, MessageSquare, ExternalLink, Save } from "lucide-react";
import { useState } from "react";

export default function ProfilePage() {
  const [isSaving, setIsSaving] = useState(false);

  const handleSave = () => {
    setIsSaving(true);
    setTimeout(() => setIsSaving(false), 1000);
  };

  const chatHistory = [
    { id: 1, date: "Jan 15, 2024", project: "Memorial Hospital", snippet: "Can you analyze the HVAC changes in Bulletin 04?", status: "Completed" },
    { id: 2, date: "Jan 14, 2024", project: "Downtown Lab", snippet: "What's the cost impact of moving the partition wall?", status: "Completed" },
    { id: 3, date: "Jan 12, 2024", project: "Memorial Hospital", snippet: "Generate a summary report for the structural changes", status: "Completed" },
  ];

  const teamMembers = [
    { name: "Sarah Chen", email: "sarah@buildcorps.com", role: "Project Manager", status: "Active" },
    { name: "Mike Ross", email: "mike@buildcorps.com", role: "Estimator", status: "Active" },
    { name: "David Kim", email: "david@external.com", role: "Viewer", status: "Invited" },
  ];

  return (
    <DashboardLayout>
      <div className="p-8 max-w-5xl mx-auto space-y-8">
        <div className="flex items-center gap-6">
          <Avatar className="w-20 h-20 border-4 border-background shadow-lg">
            <AvatarImage src="https://github.com/shadcn.png" />
            <AvatarFallback className="text-2xl">AM</AvatarFallback>
          </Avatar>
          <div>
            <h1 className="text-3xl font-bold font-display tracking-tight">Alex Morgan</h1>
            <p className="text-muted-foreground">Project Manager at BuildCorps Construction</p>
            <div className="flex items-center gap-2 mt-2">
              <Badge variant="outline" className="bg-primary/5">
                <Shield className="w-3 h-3 mr-1" /> Admin
              </Badge>
            </div>
          </div>
        </div>

        <Tabs defaultValue="profile" className="space-y-6">
          <TabsList>
            <TabsTrigger value="profile">Profile</TabsTrigger>
            <TabsTrigger value="team">Team & Invites</TabsTrigger>
            <TabsTrigger value="history">Chat History</TabsTrigger>
          </TabsList>

          {/* Profile Tab */}
          <TabsContent value="profile">
            <Card>
              <CardHeader>
                <CardTitle>Personal Information</CardTitle>
                <CardDescription>Update your profile details and contact information.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="grid md:grid-cols-2 gap-6">
                  <div className="space-y-2">
                    <Label htmlFor="name">Full Name</Label>
                    <div className="relative">
                      <User className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                      <Input id="name" defaultValue="Alex Morgan" className="pl-9" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="title">Job Title</Label>
                    <Input id="title" defaultValue="Project Manager" />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="company">Company</Label>
                    <div className="relative">
                      <Building2 className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                      <Input id="company" defaultValue="BuildCorps Construction" className="pl-9" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="phone">Phone</Label>
                    <div className="relative">
                      <Phone className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                      <Input id="phone" defaultValue="+1 (555) 123-4567" className="pl-9" />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                      <Input id="email" defaultValue="alex@buildcorps.com" className="pl-9" disabled />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label>Role & Permissions</Label>
                    <Select defaultValue="admin" disabled>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="admin">Admin</SelectItem>
                        <SelectItem value="member">Member</SelectItem>
                        <SelectItem value="viewer">Viewer</SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">Only organization admins can change roles.</p>
                  </div>
                </div>
              </CardContent>
              <CardFooter className="border-t border-border px-6 py-4">
                <Button onClick={handleSave} disabled={isSaving}>
                  <Save className="w-4 h-4 mr-2" />
                  {isSaving ? "Saving..." : "Save Changes"}
                </Button>
              </CardFooter>
            </Card>
          </TabsContent>

          {/* Team & Invites Tab */}
          <TabsContent value="team" className="space-y-6">
            <Card>
              <CardHeader>
                <CardTitle>Invite Teammates</CardTitle>
                <CardDescription>Add new members to your organization.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex gap-4">
                  <div className="flex-1 relative">
                    <Mail className="absolute left-3 top-3 w-4 h-4 text-muted-foreground" />
                    <Input placeholder="colleague@company.com" className="pl-9" />
                  </div>
                  <Select defaultValue="member">
                    <SelectTrigger className="w-[140px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="admin">Admin</SelectItem>
                      <SelectItem value="member">Member</SelectItem>
                      <SelectItem value="viewer">Viewer</SelectItem>
                    </SelectContent>
                  </Select>
                  <Button>
                    <UserPlus className="w-4 h-4 mr-2" /> Send Invite
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Team Members</CardTitle>
                <CardDescription>Manage your organization's team.</CardDescription>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {teamMembers.map((member, i) => (
                    <div key={i} className="flex items-center justify-between p-4 rounded-lg border border-border">
                      <div className="flex items-center gap-4">
                        <Avatar>
                          <AvatarFallback>{member.name.split(" ").map(n => n[0]).join("")}</AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-medium">{member.name}</p>
                          <p className="text-sm text-muted-foreground">{member.email}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <Badge variant={member.status === "Active" ? "outline" : "secondary"}>{member.status}</Badge>
                        <Select defaultValue={member.role.toLowerCase().replace(" ", "-")}>
                          <SelectTrigger className="w-[140px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="admin">Admin</SelectItem>
                            <SelectItem value="project-manager">Project Manager</SelectItem>
                            <SelectItem value="estimator">Estimator</SelectItem>
                            <SelectItem value="viewer">Viewer</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Chat History Tab */}
          <TabsContent value="history">
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <MessageSquare className="w-5 h-5" /> AI Chat History
                </CardTitle>
                <CardDescription>Your past conversations with BuildTrace AI.</CardDescription>
              </CardHeader>
              <CardContent>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Date</TableHead>
                      <TableHead>Project</TableHead>
                      <TableHead className="w-[40%]">Last Message</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Action</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {chatHistory.map((chat) => (
                      <TableRow key={chat.id}>
                        <TableCell className="font-medium">{chat.date}</TableCell>
                        <TableCell>{chat.project}</TableCell>
                        <TableCell className="text-muted-foreground truncate max-w-[300px]">{chat.snippet}</TableCell>
                        <TableCell>
                          <Badge variant="outline">{chat.status}</Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button variant="ghost" size="sm">
                            Open <ExternalLink className="w-3 h-3 ml-1" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
