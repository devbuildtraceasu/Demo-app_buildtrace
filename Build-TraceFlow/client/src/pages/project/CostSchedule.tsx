import DashboardLayout from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend } from 'recharts';
import { Download, Calendar } from "lucide-react";

export default function CostSchedule() {
  const costData = [
    { name: 'Framing', cost: 12000 },
    { name: 'HVAC', cost: 8000 },
    { name: 'Electrical', cost: 4500 },
    { name: 'Plumbing', cost: 3200 },
    { name: 'Doors', cost: 2500 },
    { name: 'Millwork', cost: -1200 },
  ];

  const scheduleData = [
    { name: 'Delayed', value: 4, color: '#EF4444' },
    { name: 'On Track', value: 12, color: '#10B981' },
    { name: 'Accelerated', value: 2, color: '#3B82F6' },
  ];

  return (
    <DashboardLayout>
      <div className="p-8 max-w-7xl mx-auto space-y-8">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold font-display tracking-tight">Cost & Schedule Impact</h1>
            <p className="text-muted-foreground">Analysis based on detected drawing changes in Bulletin 04.</p>
          </div>
          <Button variant="outline">
            <Download className="mr-2 w-4 h-4" /> Export Report
          </Button>
        </div>

        <div className="grid md:grid-cols-2 gap-8">
          <Card className="col-span-1">
            <CardHeader>
              <CardTitle>Cost Impact by Trade</CardTitle>
              <CardDescription>Estimated direct costs from geometric changes</CardDescription>
            </CardHeader>
            <CardContent className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={costData} layout="vertical" margin={{ left: 20 }}>
                  <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                  <XAxis type="number" />
                  <YAxis dataKey="name" type="category" width={80} tick={{fontSize: 12}} />
                  <Tooltip 
                    cursor={{fill: 'transparent'}}
                    contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                  />
                  <Bar dataKey="cost" fill="#0F172A" radius={[0, 4, 4, 0]}>
                    {costData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.cost > 0 ? '#0F172A' : '#10B981'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <Card className="col-span-1">
            <CardHeader>
              <CardTitle>Schedule Risk Analysis</CardTitle>
              <CardDescription>Impact on critical path activities</CardDescription>
            </CardHeader>
            <CardContent className="h-[300px]">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={scheduleData}
                    cx="50%"
                    cy="50%"
                    innerRadius={60}
                    outerRadius={80}
                    paddingAngle={5}
                    dataKey="value"
                  >
                    {scheduleData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip />
                  <Legend verticalAlign="bottom" height={36}/>
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>Detailed Breakdown</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border border-border">
              <div className="grid grid-cols-5 bg-muted/30 p-4 font-medium text-sm">
                <div className="col-span-2">Description</div>
                <div>Trade</div>
                <div>Cost Est.</div>
                <div>Schedule Impact</div>
              </div>
              {[
                { desc: "Wall Partition Moved - Room 104", trade: "Framing", cost: "$12,000", time: "+2 Days" },
                { desc: "New Door Added - Corridor", trade: "Doors", cost: "$2,500", time: "+1 Day" },
                { desc: "Duct Rerouted above Lab", trade: "HVAC", cost: "$8,000", time: "+1 Day" },
                { desc: "Millwork Deleted - Reception", trade: "Millwork", cost: "-$1,200", time: "0 Days" },
              ].map((item, i) => (
                <div key={i} className="grid grid-cols-5 p-4 border-t border-border text-sm hover:bg-muted/10">
                   <div className="col-span-2 font-medium">{item.desc}</div>
                   <div className="text-muted-foreground">{item.trade}</div>
                   <div className={item.cost.startsWith('-') ? "text-green-600" : ""}>{item.cost}</div>
                   <div className="flex items-center gap-2">
                     <Calendar className="w-3 h-3 text-muted-foreground" />
                     {item.time}
                   </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
