import { Link } from "wouter";
import { Button } from "@/components/ui/button";
import { ArrowRight, Layers, CheckCircle2, TrendingUp, ShieldCheck } from "lucide-react";
import heroBg from "@assets/generated_images/minimalist_architectural_wireframe_hero_background.png";
import logo from "@assets/BuildTrace_Logo_1767832159404.jpg";

export default function Landing() {
  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">
      {/* Navigation */}
      <nav className="border-b border-border/40 backdrop-blur-sm sticky top-0 z-50 bg-background/80">
        <div className="container mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <img src={logo} alt="BuildTrace" className="w-8 h-8 rounded-md" />
            <span className="text-xl font-bold tracking-tight font-display">BuildTrace</span>
          </div>
          <div className="hidden md:flex items-center gap-8 text-sm font-medium text-muted-foreground">
            <a href="#how-it-works" className="hover:text-foreground transition-colors">How it works</a>
            <a href="#features" className="hover:text-foreground transition-colors">Features</a>
            <a href="#pricing" className="hover:text-foreground transition-colors">Pricing</a>
          </div>
          <div className="flex items-center gap-4">
            <Link href="/auth">
              <Button variant="ghost" className="text-sm">Sign In</Button>
            </Link>
            <Link href="/try-compare">
              <Button className="font-medium">Compare Drawings</Button>
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="relative pt-20 pb-32 overflow-hidden">
        <div className="container mx-auto px-6 relative z-10">
          <div className="max-w-3xl">
            <h1 className="text-5xl md:text-7xl font-bold font-display tracking-tight text-foreground mb-6 leading-[1.1]">
              Stop the rework.<br />
              <span className="text-muted-foreground">Never miss a drawing change again.</span>
            </h1>
            <p className="text-xl text-muted-foreground mb-10 max-w-xl leading-relaxed">
              AI-powered drawing comparison that detects real scope changes, not just clouds.
              Get instant cost and schedule impact insights.
            </p>
            <div className="flex flex-col sm:flex-row gap-4">
              <Link href="/try-compare">
                <Button size="lg" className="h-12 px-8 text-base">
                  Compare Drawings Now
                  <ArrowRight className="ml-2 w-4 h-4" />
                </Button>
              </Link>
              <Link href="#demo">
                <Button size="lg" variant="outline" className="h-12 px-8 text-base bg-white/50 backdrop-blur-sm">
                  Watch demo
                </Button>
              </Link>
            </div>
          </div>
        </div>
        
        {/* Hero Image / Graphic */}
        <div className="absolute top-0 right-0 w-1/2 h-full -z-10 opacity-40 pointer-events-none hidden lg:block">
           <div className="absolute inset-0 bg-gradient-to-l from-transparent to-background" />
           <div className="absolute inset-0 bg-gradient-to-b from-transparent to-background" />
           <img 
             src={heroBg} 
             alt="Architectural Grid" 
             className="w-full h-full object-cover mix-blend-multiply opacity-50"
           />
        </div>
      </section>

      {/* How it Works */}
      <section id="how-it-works" className="py-24 bg-white">
        <div className="container mx-auto px-6">
          <div className="mb-16">
            <h2 className="text-3xl md:text-4xl font-bold font-display mb-4">It's simpler than you think.</h2>
            <p className="text-lg text-muted-foreground">No training required. Start your first comparison in minutes.</p>
          </div>

          <div className="grid md:grid-cols-3 gap-12">
            {[
              {
                step: "01",
                title: "Upload Drawings",
                desc: "Drag and drop your previous and revised PDF sets. We automatically extract sheet numbers and titles.",
                icon: <Layers className="w-6 h-6" />
              },
              {
                step: "02",
                title: "AI Analysis",
                desc: "Our engine overlays the sheets and identifies geometric changes, filtering out noise and minor shifts.",
                icon: <CheckCircle2 className="w-6 h-6" />
              },
              {
                step: "03",
                title: "Review Impacts",
                desc: "See a prioritized list of changes with estimated cost and schedule implications for each trade.",
                icon: <TrendingUp className="w-6 h-6" />
              }
            ].map((item, i) => (
              <div key={i} className="group p-8 rounded-2xl border border-border bg-card hover:shadow-lg transition-all duration-300 relative overflow-hidden">
                <div className="absolute top-0 right-0 p-8 text-9xl font-bold text-muted/20 select-none -translate-y-8 translate-x-8 group-hover:translate-x-4 transition-transform font-display">
                  {item.step}
                </div>
                <div className="w-12 h-12 rounded-lg bg-primary/5 text-primary flex items-center justify-center mb-6 relative z-10">
                  {item.icon}
                </div>
                <h3 className="text-xl font-bold mb-3 relative z-10">{item.title}</h3>
                <p className="text-muted-foreground leading-relaxed relative z-10">
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24 bg-primary text-primary-foreground relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('https://grainy-gradients.vercel.app/noise.svg')] opacity-10"></div>
        <div className="container mx-auto px-6 text-center relative z-10">
          <h2 className="text-3xl md:text-5xl font-bold font-display mb-6">Ready to see the difference?</h2>
          <p className="text-primary-foreground/80 text-xl mb-10 max-w-2xl mx-auto">
            Try BuildTrace on your current project. The first 10 sheets are free.
          </p>
          <Link href="/try-compare">
            <Button size="lg" variant="secondary" className="h-14 px-10 text-lg font-semibold text-primary">
              Compare Drawings Free
            </Button>
          </Link>
          <p className="mt-6 text-sm text-primary-foreground/60 flex items-center justify-center gap-2">
            <ShieldCheck className="w-4 h-4" />
            SOC2 Compliant & Enterprise Ready
          </p>
        </div>
      </section>

      {/* Footer */}
      <footer className="py-12 border-t border-border bg-muted/20">
        <div className="container mx-auto px-6 flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex items-center gap-2">
            <img src={logo} alt="BuildTrace" className="w-6 h-6 rounded-sm" />
            <span className="font-bold font-display text-foreground">BuildTrace</span>
          </div>
          <div className="text-sm text-muted-foreground">
            © 2024 BuildTrace Inc. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}
