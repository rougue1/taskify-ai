"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LogOut, MessageSquare, Moon, Sparkles, Sun } from "lucide-react";
import { useTheme } from "next-themes";

import { Button } from "@/components/ui/button";
import { healthCheck } from "@/lib/api";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/authStore";

interface HeaderProps {
  onToggleChat?: () => void;
}

type Connectivity = "checking" | "connected" | "disconnected";

export function Header({ onToggleChat }: HeaderProps) {
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const [mounted, setMounted] = useState(false);
  const [status, setStatus] = useState<Connectivity>("checking");

  const handleLogout = () => {
    logout();
    router.replace("/login");
  };

  useEffect(() => {
    setMounted(true);
  }, []);

  // Poll backend connectivity every 30 seconds.
  useEffect(() => {
    let active = true;
    const check = async () => {
      const result = await healthCheck();
      if (active) {
        setStatus(result.status === "ok" ? "connected" : "disconnected");
      }
    };
    check();
    const interval = setInterval(check, 30_000);
    return () => {
      active = false;
      clearInterval(interval);
    };
  }, []);

  const dotColor =
    status === "connected"
      ? "bg-green-500"
      : status === "disconnected"
        ? "bg-red-500"
        : "bg-yellow-400";

  const dotLabel =
    status === "connected"
      ? "Connected"
      : status === "disconnected"
        ? "Offline"
        : "Checking";

  return (
    <header className="flex items-center justify-between border-b px-4 py-3 sm:px-6">
      <div className="flex items-center gap-2">
        <Sparkles className="text-primary h-5 w-5" />
        <span className="text-lg font-semibold tracking-tight">Taskify</span>
        <span className="text-muted-foreground hidden text-xs sm:inline">
          AI Task Manager
        </span>
      </div>

      <div className="flex items-center gap-3">
        <div
          className="flex items-center gap-1.5"
          title={`Backend: ${dotLabel}`}
          aria-label={`Backend ${dotLabel}`}
        >
          <span
            className={cn(
              "h-2.5 w-2.5 rounded-full transition-colors",
              dotColor,
            )}
          />
          <span className="text-muted-foreground hidden text-xs sm:inline">
            {dotLabel}
          </span>
        </div>

        {onToggleChat && (
          <Button variant="ghost" size="sm" onClick={onToggleChat}>
            <MessageSquare className="h-4 w-4" />
            <span className="hidden sm:inline">Chat</span>
          </Button>
        )}

        <Button
          variant="ghost"
          size="icon"
          aria-label="Toggle theme"
          onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
        >
          {mounted && resolvedTheme === "dark" ? (
            <Sun className="h-4 w-4" />
          ) : (
            <Moon className="h-4 w-4" />
          )}
        </Button>

        {user && (
          <>
            <span
              className="text-muted-foreground hidden max-w-[14rem] truncate text-xs md:inline"
              title={user.email}
            >
              {user.email}
            </span>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Log out"
              title="Log out"
              onClick={handleLogout}
            >
              <LogOut className="h-4 w-4" />
            </Button>
          </>
        )}
      </div>
    </header>
  );
}
