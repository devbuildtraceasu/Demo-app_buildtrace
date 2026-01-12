import DashboardLayout from "@/components/layout/DashboardLayout";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription, CardFooter } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Coins, TrendingDown, ShoppingCart, Check, Zap } from "lucide-react";
import { useState } from "react";

export default function CreditsPage() {
  const [selectedPack, setSelectedPack] = useState<string | null>(null);

  const creditPacks = [
    { id: "5k", credits: 5000, price: 500, popular: false },
    { id: "10k", credits: 10000, price: 1000, popular: true },
    { id: "25k", credits: 25000, price: 2500, popular: false },
  ];

  const usageHistory = [
    { date: "Jan 15, 2024", project: "Memorial Hospital Expansion", action: "Overlay + Analysis", credits: 150 },
    { date: "Jan 14, 2024", project: "Downtown Lab Complex", action: "Overlay Generation", credits: 80 },
    { date: "Jan 12, 2024", project: "Memorial Hospital Expansion", action: "Cost Impact Report", credits: 50 },
    { date: "Jan 10, 2024", project: "Seaport Multifamily", action: "Overlay + Analysis", credits: 120 },
    { date: "Jan 08, 2024", project: "Downtown Lab Complex", action: "Schedule Analysis", credits: 40 },
  ];

  const currentBalance = 2450;

  return (
    <DashboardLayout>
      <div className="p-8 max-w-5xl mx-auto space-y-8">
        <div>
          <h1 className="text-3xl font-bold font-display tracking-tight">Credits</h1>
          <p className="text-muted-foreground">Manage your BuildTrace credits and purchase more.</p>
        </div>

        {/* Balance Card */}
        <div className="grid md:grid-cols-3 gap-6">
          <Card className="md:col-span-2 bg-gradient-to-br from-primary to-primary/80 text-primary-foreground relative overflow-hidden">
            <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-10" />
            <CardContent className="p-8 relative z-10">
              <div className="flex items-center gap-3 mb-4">
                <div className="w-12 h-12 rounded-full bg-white/20 flex items-center justify-center">
                  <Coins className="w-6 h-6" />
                </div>
                <div>
                  <p className="text-sm text-primary-foreground/70 font-medium">Current Balance</p>
                  <p className="text-4xl font-bold font-display">{currentBalance.toLocaleString()}</p>
                </div>
              </div>
              <p className="text-primary-foreground/60 text-sm">
                ≈ ${(currentBalance / 10).toLocaleString()} USD value
              </p>
              <p className="text-xs text-primary-foreground/50 mt-2">10 credits = $1</p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">This Month</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-2">
                <TrendingDown className="w-5 h-5 text-amber-500" />
                <span className="text-2xl font-bold font-display">440</span>
              </div>
              <p className="text-sm text-muted-foreground mt-1">Credits used</p>
            </CardContent>
          </Card>
        </div>

        {/* Purchase Credits */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShoppingCart className="w-5 h-5" /> Purchase Credits
            </CardTitle>
            <CardDescription>Select a credit pack to top up your balance.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid md:grid-cols-3 gap-4">
              {creditPacks.map((pack) => (
                <div
                  key={pack.id}
                  onClick={() => setSelectedPack(pack.id)}
                  className={`
                    relative p-6 rounded-xl border-2 cursor-pointer transition-all
                    ${selectedPack === pack.id 
                      ? 'border-primary bg-primary/5 ring-2 ring-primary/20' 
                      : 'border-border hover:border-primary/50 hover:bg-muted/30'}
                  `}
                >
                  {pack.popular && (
                    <Badge className="absolute -top-2 left-1/2 -translate-x-1/2 bg-primary">
                      <Zap className="w-3 h-3 mr-1" /> Most Popular
                    </Badge>
                  )}
                  <div className="text-center">
                    <p className="text-3xl font-bold font-display">{pack.credits.toLocaleString()}</p>
                    <p className="text-sm text-muted-foreground mb-4">credits</p>
                    <p className="text-2xl font-semibold">${pack.price}</p>
                    <p className="text-xs text-muted-foreground">USD</p>
                  </div>
                  {selectedPack === pack.id && (
                    <div className="absolute top-3 right-3 w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center">
                      <Check className="w-4 h-4" />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
          <CardFooter className="border-t border-border px-6 py-4 flex justify-between items-center">
            <p className="text-sm text-muted-foreground">
              {selectedPack 
                ? `Selected: ${creditPacks.find(p => p.id === selectedPack)?.credits.toLocaleString()} credits`
                : "Select a pack to continue"}
            </p>
            <Button disabled={!selectedPack} size="lg">
              Buy Credits
            </Button>
          </CardFooter>
        </Card>

        {/* Usage History */}
        <Card>
          <CardHeader>
            <CardTitle>Recent Usage</CardTitle>
            <CardDescription>Your credit consumption history.</CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Date</TableHead>
                  <TableHead>Project</TableHead>
                  <TableHead>Action</TableHead>
                  <TableHead className="text-right">Credits Used</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {usageHistory.map((item, i) => (
                  <TableRow key={i}>
                    <TableCell className="font-medium">{item.date}</TableCell>
                    <TableCell>{item.project}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{item.action}</Badge>
                    </TableCell>
                    <TableCell className="text-right font-mono text-muted-foreground">-{item.credits}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
