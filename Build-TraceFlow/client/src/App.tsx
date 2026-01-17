import { Switch, Route } from "wouter";
import { queryClient } from "./lib/queryClient";
import { QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/toaster";
import { TooltipProvider } from "@/components/ui/tooltip";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import NotFound from "@/pages/not-found";

import Landing from "@/pages/Landing";
import AuthPage from "@/pages/auth/AuthPage";
import ForgotPasswordPage from "@/pages/auth/ForgotPasswordPage";
import ResetPasswordPage from "@/pages/auth/ResetPasswordPage";
import ProjectSetup from "@/pages/onboarding/ProjectSetup";
import ProjectList from "@/pages/dashboard/ProjectList";
import ProjectDashboard from "@/pages/project/ProjectDashboard";
import NewOverlay from "@/pages/project/NewOverlay";
import OverlayViewer from "@/pages/project/OverlayViewer";
import CostSchedule from "@/pages/project/CostSchedule";
import Drawings from "@/pages/project/Drawings";
import Settings from "@/pages/settings/Settings";
import CreditsPage from "@/pages/settings/CreditsPage";
import ProfilePage from "@/pages/profile/ProfilePage";
import GodMode from "@/pages/admin/GodMode";
import TryCompare from "@/pages/public/TryCompare";

function Router() {
  return (
    <Switch>
      <Route path="/" component={Landing} />
      <Route path="/try-compare" component={TryCompare} />
      <Route path="/auth" component={AuthPage} />
      <Route path="/forgot-password" component={ForgotPasswordPage} />
      <Route path="/reset-password" component={ResetPasswordPage} />
      <Route path="/onboarding" component={ProjectSetup} />
      
      {/* Dashboard Routes */}
      <Route path="/dashboard" component={ProjectList} />
      <Route path="/settings" component={Settings} />
      <Route path="/credits" component={CreditsPage} />
      <Route path="/profile" component={ProfilePage} />
      
      {/* Project Routes */}
      <Route path="/project/:id" component={ProjectDashboard} />
      <Route path="/project/:id/new-overlay" component={NewOverlay} />
      <Route path="/project/:id/overlay/:comparisonId" component={OverlayViewer} />
      <Route path="/project/:id/overlay" component={OverlayViewer} />
      <Route path="/project/:id/cost" component={CostSchedule} />
      <Route path="/project/:id/drawings" component={Drawings} />
      
      {/* Admin Route */}
      <Route path="/admin" component={GodMode} />
      
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </QueryClientProvider>
    </ErrorBoundary>
  );
}

export default App;
