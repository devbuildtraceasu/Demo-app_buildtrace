import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Link } from "wouter";
import { useState } from "react";
import { Loader2, ArrowLeft } from "lucide-react";
import logo from "@assets/BuildTrace_Logo_1767832159404.jpg";
import api from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

export default function ForgotPasswordPage() {
  const [isLoading, setIsLoading] = useState(false);
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const { toast } = useToast();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      await api.auth.forgotPassword(email);
      setSubmitted(true);
      toast({
        title: "Email Sent",
        description: "If an account exists with this email, you'll receive a password reset link",
      });
    } catch (error) {
      toast({
        title: "Request Failed",
        description: error instanceof Error ? error.message : "Could not process request",
        variant: "destructive",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-muted/30 flex items-center justify-center p-4">
      <div className="w-full max-w-md space-y-8">
        <div className="text-center space-y-2">
          <img src={logo} alt="BuildTrace" className="w-12 h-12 rounded-lg mb-4 inline-block" />
          <h1 className="text-3xl font-bold font-display tracking-tight">Forgot Password</h1>
          <p className="text-muted-foreground">
            Enter your email and we'll send you a reset link
          </p>
        </div>

        <Card className="border-border shadow-lg">
          <CardHeader>
            <CardTitle>Reset Password</CardTitle>
            <CardDescription>Enter the email associated with your account</CardDescription>
          </CardHeader>
          <CardContent>
            {submitted ? (
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
                  <h3 className="font-semibold text-lg">Check your email</h3>
                  <p className="text-sm text-muted-foreground">
                    If an account exists for {email}, you'll receive a password reset link shortly.
                  </p>
                </div>
              </div>
            ) : (
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="email">Email</Label>
                  <Input
                    id="email"
                    type="email"
                    placeholder="name@company.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    required
                  />
                </div>
                <Button type="submit" className="w-full" disabled={isLoading}>
                  {isLoading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
                  Send Reset Link
                </Button>
              </form>
            )}
          </CardContent>
          <CardFooter className="flex justify-center border-t border-border pt-6">
            <Link href="/auth" className="text-sm text-muted-foreground hover:text-primary flex items-center gap-1">
              <ArrowLeft className="w-4 h-4" />
              Back to sign in
            </Link>
          </CardFooter>
        </Card>
      </div>
    </div>
  );
}
