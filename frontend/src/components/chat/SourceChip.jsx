import React, { useState } from "react";
import { FileText } from "lucide-react";
import { cn } from "../../lib/utils";
import { CitationPopover } from "./CitationPopover";

export function SourceChip({ source, index }) {
  const [open, setOpen] = useState(false);
  
  return (
    <CitationPopover source={source} open={open} onOpenChange={setOpen}>
      <button
        onClick={() => setOpen(true)}
        className={cn(
          "inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium",
          "bg-secondary hover:bg-secondary/80 text-secondary-foreground",
          "transition-colors border border-border",
          "focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-1"
        )}
        aria-label={`Source ${index + 1}: ${source.preview?.slice(0, 50) || "Document"}`}
      >
        <FileText className="h-3 w-3" />
        <span>Source {index + 1}</span>
        {source.score && (
          <span className="text-muted-foreground">
            {(source.score * 100).toFixed(0)}%
          </span>
        )}
      </button>
    </CitationPopover>
  );
}