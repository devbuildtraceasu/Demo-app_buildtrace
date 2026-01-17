import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Link, useLocation, useSearch } from "wouter";
import { useState } from "react";
import { Loader2 } from "lucide-react";
import logo from "@assets/BuildTrace_Logo_1767832159404.jpg";
import api from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

export default function ResetPasswordPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [success, setSuccess] = useState(false);
  const searchString = useSearch();
  const [, setLocation] = useLocation();
  const { toast } = useToast();

  const token = new URLSearchParams(searchString).get("token");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password !== confirmPassword) {
      toast({
        title: "Passwords Don't Match",
        description: "Please ensure both passwords are the same",
        variant: "destructive",
      });
      return;
    }

    if (!token) {
      toast({
        title: "Invalid Link",
        description: "Reset token is missing",
        variant: "destructive",
      });
      return;
    }

    setIsLoading(true);

    try {
      await api.auth.resetPassword(token, password);
      setSuccess(true);
      toast({
        title: "Password Reset",
        description: "Your password has been reset successfully",
      });

      setTimeout(() => {
        setLocation("/auth");
      }, 2000);
    } catch (error) {
      toast({
        title: "Reset Failed",
        description: error instanceof Error ? error.message : "Invalid or expired reset token",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="min-h-screen bg-muted/30 flex items-center justify-center p-4">
        <Card className="max-w-md w-full">
          <CardHeader>
            <CardTitle>Invalid Reset Link</CardTitle>
            <CardDescription>This password reset link is invalid or expired</CardDescription>
          </CardHeader>
          <CardFooter>
            <Link href="/forgot-password">
              <Button variant="outline" className="w-full">
                Request New Link
              </Button>
            </Link>
          </CardFooter>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-muted/30 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center space-y-2">
          <img src={logo} alt="BuildTrace" className="w-12 h-12 rounded-lg mb-4 inline-block" />
          <h1 className="text-3xl font-bold font-display tracking-tight">Reset Password</h1>
          <p className="text-muted-foreground">Enter your new password</p>
        </div>

        <Card className="border-border shadow-lg">
          <CardHeader>
            <CardTitle>Create New Password</CardTitle>
            <CardDescription>Choose a strong password for your account</CardDescription>
          </CardHeader>
          <CardContent>
            {success ? (
              <div className="text-center py-6 space-y-4">
                <div className="w-16 h-16 mx-auto bg-green-100 rounded-full flex items-center justify-center">
                  <svg
                    className="w-8 h-8 text-green-600"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </div>
                <div className="space-y-2">
                  <h3 className="font-semibold text-lg">Password Reset Successfully</h3>
                  <p className="text-sm text-muted-foreground">
                    Redirecting you to sign in...
                  </p>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="password">New Password</Label>
                  <Input
                    id="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={8}
                  />
                  <p className="text-xs text-muted-foreground">
                    Must be at least 8 characters
                  </p>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="confirmPassword">Confirm Password</Label>
                  <Input
                    id="confirmPassword"
                    type="password"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    required
                    minLength={8}
                  />
                </div>
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                  Reset Password
                </Button>
              </form>
            )}
          </CardContent>
          {!success && (
            <CardFooter className="flex justify-center border-t border-border pt-6">
              <Link href="/auth" className="text-sm text-muted-foreground hover:text-primary">
                Back to sign in
              </Link>
            </CardFooter>
          )}
        </Card>
      </div>
    </div>
  );
}
