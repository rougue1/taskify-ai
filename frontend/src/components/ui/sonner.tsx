"use client";

import { useTheme } from "next-themes";
import { Toaster as Sonner, type ToasterProps } from "sonner";

// Theme-aware toast container. Picks up the active light/dark theme from
// next-themes so toasts match the rest of the UI.
export function Toaster(props: ToasterProps) {
  const { resolvedTheme } = useTheme();
  return (
    <Sonner
      theme={(resolvedTheme as ToasterProps["theme"]) ?? "system"}
      richColors
      closeButton
      position="top-right"
      {...props}
    />
  );
}
