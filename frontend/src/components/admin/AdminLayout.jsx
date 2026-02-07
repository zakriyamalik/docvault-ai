import React from "react";
import { Link, useLocation } from "react-router-dom";
import { FileText, AlertCircle, MessageSquare, LayoutDashboard } from "lucide-react";
import { cn } from "../../lib/utils";
import { Button } from "../ui/Button";

const navItems = [
  { path: "/admin", label: "Documents", icon: FileText },
  { path: "/admin/dlq", label: "Dead Letter Queue", icon: AlertCircle },
  { path: "/chat", label: "Chat", icon: MessageSquare },
];

export function AdminLayout({ children }) {
  const location = useLocation();

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <LayoutDashboard className="h-6 w-6 text-primary" />
            <h1 className="text-xl font-bold">Admin Dashboard</h1>
          </div>
          <div className="flex items-center gap-2">
            {navItems.map((item) => (
              <Button
                key={item.path}
                variant={location.pathname === item.path ? "default" : "ghost"}
                size="sm"
                asChild
              >
                <Link to={item.path} className="flex items-center gap-2">
                  <item.icon className="h-4 w-4" />
                  {item.label}
                </Link>
              </Button>
            ))}
          </div>
        </div>
      </header>
      <main className="container mx-auto px-4 py-8">{children}</main>
    </div>
  );
}