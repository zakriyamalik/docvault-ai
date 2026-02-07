import React from "react";
import { Outlet } from "react-router-dom";
import { Toaster } from "../ui/Toaster";

export default function RootLayout() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Outlet />
      <Toaster />
    </div>
  );
}