"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { Loader2 } from "lucide-react";

import { useAuthStore } from "@/store/authStore";

// Wraps protected content. Waits for the persisted auth state to hydrate, then
// redirects unauthenticated visitors to /login. While a valid token exists but
// the user object is missing (e.g. right after a reload), it loads /me.
export function AuthGate({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const hydrated = useAuthStore((s) => s.hydrated);
  const accessToken = useAuthStore((s) => s.accessToken);
  const user = useAuthStore((s) => s.user);
  const loadUser = useAuthStore((s) => s.loadUser);

  useEffect(() => {
    if (hydrated && !accessToken) {
      router.replace("/login");
    }
  }, [hydrated, accessToken, router]);

  useEffect(() => {
    if (hydrated && accessToken && !user) {
      void loadUser();
    }
  }, [hydrated, accessToken, user, loadUser]);

  if (!hydrated || !accessToken) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="text-muted-foreground h-6 w-6 animate-spin" />
      </div>
    );
  }

  return <>{children}</>;
}
