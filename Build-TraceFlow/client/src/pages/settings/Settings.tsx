import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Shield, CreditCard, Users, Building } from "lucide-react";
import logo from "@assets/BuildTrace_Logo_1767832159404.jpg";

export default function Settings() {
  return (
    <DashboardLayout>
      <div className="p-8 max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold font-display tracking-tight mb-8">Settings</h1>
        
        <Tabs defaultValue="team" className="space-y-6">
          <TabsList className="grid w-full max-w-md grid-cols-4">
            <TabsTrigger value="organization">General</TabsTrigger>
            <TabsTrigger value="team">Team</TabsTrigger>
            <TabsTrigger value="security">Security</TabsTrigger>
            <TabsTrigger value="billing">Billing</TabsTrigger>
          </TabsList>

          {/* Organization Settings */}
          <TabsContent value="organization">
             <Card>
               <CardHeader>
                 <CardTitle>Organization Profile</CardTitle>
                 <CardDescription>Manage your company details and branding.</CardDescription>
               </CardHeader>
               <CardContent className="space-y-4">
                 <div className="flex items-center gap-4">
                   <img src={logo} alt="BuildTrace" className="w-16 h-16 rounded-lg border border-border" />
                   <Button variant="outline">Change Logo</Button>
                 </div>
                 <div className="grid gap-4 py-4">
                   <div className="grid grid-cols-4 items-center gap-4">
                     <Label className="text-right">Org Name</Label>
                     <Input defaultValue="BuildCorps Construction" className="col-span-3" />
                   </div>
                   <div className="grid grid-cols-4 items-center gap-4">
                     <Label className="text-right">Domain</Label>
                     <Input defaultValue="buildcorps.com" className="col-span-3" disabled />
                   </div>
                 </div>
               </CardContent>
               <CardFooter className="border-t border-border px-6 py-4">
                 <Button>Save Changes</Button>
               </CardFooter>
             </Card>
          </TabsContent>

          {/* Team / User Management */}
          <TabsContent value="team">
            <Card>
              <CardHeader>
                <div className="flex justify-between items-center">
                  <div>
                    <CardTitle>Team Members</CardTitle>
                    <CardDescription>Manage access and roles for your organization.</CardDescription>
                  </div>
                  <Button>
                    <Users className="mr-2 w-4 h-4" /> Invite Member
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <div className="space-y-6">
                  {[
                    { name: "Alex Morgan", email: "alex@buildcorps.com", role: "Admin", status: "Active" },
                    { name: "Sarah Chen", email: "sarah@buildcorps.com", role: "Project Manager", status: "Active" },
                    { name: "Mike Ross", email: "mike@buildcorps.com", role: "Estimator", status: "Active" },
                    { name: "David Kim", email: "david@external-consultant.com", role: "Viewer", status: "Invited" },
                  ].map((user, i) => (
                    <div key={i} className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        <Avatar>
                          <AvatarFallback>{user.name.split(" ").map(n => n[0]).join("")}</AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-medium">{user.name}</p>
                          <p className="text-sm text-muted-foreground">{user.email}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-4">
                        <Badge variant={user.status === "Active" ? "outline" : "secondary"}>{user.status}</Badge>
                        <Select defaultValue={user.role.toLowerCase().replace(" ", "-")}>
                          <SelectTrigger className="w-[140px]">
                            <SelectValue placeholder="Select role" />
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

          {/* Security / MFA */}
          <TabsContent value="security">
             <Card>
               <CardHeader>
                 <CardTitle>Security Settings</CardTitle>
                 <CardDescription>Manage authentication and access controls.</CardDescription>
               </CardHeader>
               <CardContent className="space-y-6">
                 <div className="flex items-center justify-between">
                   <div className="space-y-0.5">
                     <Label className="text-base">Multi-Factor Authentication (MFA)</Label>
                     <p className="text-sm text-muted-foreground">Require all users to log in with a second factor.</p>
                   </div>
                   <Switch />
                 </div>
                 <div className="flex items-center justify-between">
                   <div className="space-y-0.5">
                     <Label className="text-base">Single Sign-On (SSO)</Label>
                     <p className="text-sm text-muted-foreground">Enable SAML authentication via Okta or Azure AD.</p>
                   </div>
                   <Button variant="outline">Configure</Button>
                 </div>
                  <div className="flex items-center justify-between">
                   <div className="space-y-0.5">
                     <Label className="text-base">Session Timeout</Label>
                     <p className="text-sm text-muted-foreground">Automatically log out inactive users.</p>
                   </div>
                   <Select defaultValue="30">
                     <SelectTrigger className="w-[180px]">
                       <SelectValue placeholder="Select time" />
                     </SelectTrigger>
                     <SelectContent>
                       <SelectItem value="15">15 Minutes</SelectItem>
                       <SelectItem value="30">30 Minutes</SelectItem>
                       <SelectItem value="60">1 Hour</SelectItem>
                       <SelectItem value="240">4 Hours</SelectItem>
                     </SelectContent>
                   </Select>
                 </div>
               </CardContent>
             </Card>
          </TabsContent>

          {/* Billing */}
          <TabsContent value="billing">
            <Card>
              <CardHeader>
                <CardTitle>Plan & Billing</CardTitle>
                <CardDescription>Manage your subscription and payment method.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="p-4 bg-muted/30 border border-border rounded-lg flex justify-between items-center">
                   <div>
                     <h3 className="font-bold text-lg">Enterprise Plan</h3>
                     <p className="text-sm text-muted-foreground">$499/month • Billed Annually</p>
                   </div>
                   <Badge>Active</Badge>
                </div>
                <div className="grid gap-2">
                  <div className="flex justify-between text-sm">
                    <span>Projects Used</span>
                    <span className="font-medium">7 / 10</span>
                  </div>
                  <div className="h-2 w-full bg-secondary rounded-full overflow-hidden">
                    <div className="h-full bg-primary w-[70%]"></div>
                  </div>
                </div>
              </CardContent>
              <CardFooter className="border-t border-border px-6 py-4 flex justify-between">
                <Button variant="ghost" className="text-muted-foreground">View Invoices</Button>
                <Button variant="outline">Upgrade Plan</Button>
              </CardFooter>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </DashboardLayout>
  );
}
