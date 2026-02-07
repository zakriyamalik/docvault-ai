import React from "react";
import { Link2, FileText, Hash } from "lucide-react";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@radix-ui/react-popover";
import { Button } from "../ui/Button";
import { ScrollArea } from "../ui/ScrollArea";
import { cn } from "../../lib/utils";

export function CitationPopover({ children, source, open, onOpenChange }) {
  const handleViewDocument = () => {
    const url = `/admin/documents/${source.document_id}/view?chunk=${source.chunk_id}&index=${source.chunk_index}`;
    window.open(url, "_blank");
  };

  const handleCopyLink = () => {
    const url = `${window.location.origin}/admin/documents/${source.document_id}/view?chunk=${source.chunk_id}`;
    navigator.clipboard.writeText(url);
  };

  return (
    <Popover open={open} onOpenChange={onOpenChange}>
      <PopoverTrigger asChild>{children}</PopoverTrigger>
      <PopoverContent
        className={cn(
          "w-80 p-0 bg-popover text-popover-foreground",
          "rounded-lg border shadow-lg",
          "data-[state=open]:animate-in data-[state=closed]:animate-out",
          "data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
          "data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
          "z-50"
        )}
        side="top"
        align="center"
        sideOffset={4}
      >
        <div className="p-4 space-y-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-2 text-sm font-medium">
              <FileText className="h-4 w-4 text-primary" />
              <span className="truncate max-w-[180px]">
                Document {source.document_id?.slice(0, 8)}...
              </span>
            </div>
            {source.score && (
              <span className="text-xs bg-primary/10 text-primary px-2 py-0.5 rounded-full">
                {(source.score * 100).toFixed(1)}% match
              </span>
            )}
          </div>
          
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <Hash className="h-3 w-3" />
            <span>Chunk {source.chunk_index}</span>
          </div>
          
          <ScrollArea className="h-24 rounded-md bg-muted/50 p-2">
            <p className="text-xs leading-relaxed text-foreground">
              {source.preview || "No preview available"}
            </p>
          </ScrollArea>
          
          <div className="flex gap-2 pt-1">
            <Button size="sm" className="flex-1" onClick={handleViewDocument}>
              <FileText className="h-3 w-3 mr-1" />
              View
            </Button>
            <Button size="sm" variant="outline" onClick={handleCopyLink}>
              <Link2 className="h-3 w-3 mr-1" />
              Copy
            </Button>
          </div>
        </div>
      </PopoverContent>
    </Popover>
  );
}