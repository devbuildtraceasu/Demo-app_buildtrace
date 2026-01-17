import DashboardLayout from "@/components/layout/DashboardLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell, PieChart, Pie, Legend } from 'recharts';
import { Download, Calendar, Loader2 } from "lucide-react";
import { useParams, useSearch } from "wouter";
import { useQuery } from "@tanstack/react-query";
import api from "@/lib/api";
import { useMemo } from "react";

export default function CostSchedule() {
  const params = useParams<{ id: string }>();
  const projectId = params.id;
  const searchString = useSearch();
  const searchParams = new URLSearchParams(searchString);
  const comparisonId = searchParams.get('comparison');

  // Fetch analysis summary if comparison ID is provided
  const { data: analysisData, isLoading, error } = useQuery({
    queryKey: ['analysis', 'summary', comparisonId],
    queryFn: () => api.analysis.getSummary(comparisonId!),
    enabled: !!comparisonId,
  });

  // Transform changes into cost data by trade
  const costData = useMemo(() => {
    if (!analysisData?.changes) {
      // Fallback to empty data if no analysis
      return [];
    }

    // Group changes by trade and sum costs
    const tradeMap = new Map<string, number>();
    
    analysisData.changes.forEach((change: any) => {
      const trade = change.trade || 'Other';
      // Extract numeric value from cost string (e.g., "$15,000 - $20,000" -> use midpoint)
      const costStr = change.estimated_cost || '$0';
      const numbers = costStr.match(/[\d,]+/g);
      if (numbers && numbers.length > 0) {
        // Use first number or average if range
        const values = numbers.map(n => parseFloat(n.replace(/,/g, '')));
        const avgCost = values.length > 1 
          ? (values[0] + values[values.length - 1]) / 2 
          : values[0];
        tradeMap.set(trade, (tradeMap.get(trade) || 0) + avgCost);
      }
    });

    // Convert to array and sort by cost
    return Array.from(tradeMap.entries())
      .map(([name, cost]) => ({ name, cost: Math.round(cost) }))
      .sort((a, b) => Math.abs(b.cost) - Math.abs(a.cost));
  }, [analysisData]);

  // Transform changes into schedule risk data
  const scheduleData = useMemo(() => {
    if (!analysisData?.changes) {
      return [
        { name: 'Delayed', value: 0, color: '#EF4444' },
        { name: 'On Track', value: 0, color: '#10B981' },
        { name: 'Accelerated', value: 0, color: '#3B82F6' },
      ];
    }

    let delayed = 0;
    let onTrack = 0;
    let accelerated = 0;

    analysisData.changes.forEach((change: any) => {
      const scheduleStr = change.schedule_impact || '0 days';
      const days = parseInt(scheduleStr.replace(/[^0-9-]/g, '')) || 0;
      if (days > 0) delayed++;
      else if (days < 0) accelerated++;
      else onTrack++;
    });

    return [
      { name: 'Delayed', value: delayed, color: '#EF4444' },
      { name: 'On Track', value: onTrack, color: '#10B981' },
      { name: 'Accelerated', value: accelerated, color: '#3B82F6' },
    ];
  }, [analysisData]);

  // Detailed breakdown from changes
  const detailedBreakdown = useMemo(() => {
    if (!analysisData?.changes) return [];
    
    return analysisData.changes.map((change: any) => ({
      desc: `${change.title}${change.description ? ` - ${change.description}` : ''}`,
      trade: change.trade || 'Other',
      cost: change.estimated_cost || '$0',
      time: change.schedule_impact || '0 Days',
    }));
  }, [analysisData]);

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="p-8 max-w-7xl mx-auto flex items-center justify-center h-[60vh]">
          <div className="text-center space-y-4">
            <Loader2 className="w-8 h-8 animate-spin mx-auto text-muted-foreground" />
            <p className="text-muted-foreground">Loading cost & schedule analysis...</p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  if (error || !comparisonId) {
    return (
      <DashboardLayout>
        <div className="p-8 max-w-7xl mx-auto">
          <div className="text-center space-y-4 py-12">
            <h1 className="text-3xl font-bold font-display tracking-tight">Cost & Schedule Impact</h1>
            <p className="text-muted-foreground">
              {!comparisonId 
                ? "No comparison selected. Please select a comparison first."
                : "Failed to load analysis data. Please try again."}
            </p>
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const totalCost = analysisData?.summary?.total_cost_impact || 'Not calculated';
  const totalSchedule = analysisData?.summary?.total_schedule_impact || 'Not calculated';
  const analysisSummary = analysisData?.summary?.analysis_summary || 'No analysis available yet.';

  return (
    <DashboardLayout>
      <div className="p-8 max-w-7xl mx-auto space-y-8">
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold font-display tracking-tight">Cost & Schedule Impact</h1>
            <p className="text-muted-foreground">
              {analysisSummary}
            </p>
            {totalCost !== 'Not calculated' && (
              <p className="text-sm text-muted-foreground mt-1">
                Total Impact: {totalCost} • {totalSchedule}
              </p>
            )}
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
              {costData.length === 0 ? (
                <div className="flex items-center justify-center h-full text-muted-foreground">
                  No cost data available
                </div>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={costData} layout="vertical" margin={{ left: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" horizontal={false} />
                    <XAxis type="number" />
                    <YAxis dataKey="name" type="category" width={80} tick={{fontSize: 12}} />
                    <Tooltip 
                      cursor={{fill: 'transparent'}}
                      contentStyle={{ borderRadius: '8px', border: 'none', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}
                      formatter={(value: number) => `$${value.toLocaleString()}`}
                    />
                    <Bar dataKey="cost" fill="#0F172A" radius={[0, 4, 4, 0]}>
                      {costData.map((entry, index) => (
                        <Cell key={`cell-${index}`} fill={entry.cost > 0 ? '#0F172A' : '#10B981'} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              )}
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
              {detailedBreakdown.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground">
                  No detailed breakdown available
                </div>
              ) : (
                detailedBreakdown.map((item, i) => (
                <div key={i} className="grid grid-cols-5 p-4 border-t border-border text-sm hover:bg-muted/10">
                   <div className="col-span-2 font-medium">{item.desc}</div>
                   <div className="text-muted-foreground">{item.trade}</div>
                   <div className={item.cost.startsWith('-') ? "text-green-600" : ""}>{item.cost}</div>
                   <div className="flex items-center gap-2">
                     <Calendar className="w-3 h-3 text-muted-foreground" />
                     {item.time}
                   </div>
                </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
