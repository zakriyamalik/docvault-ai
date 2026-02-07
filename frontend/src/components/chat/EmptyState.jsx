import React from "react";
import { MessageSquare, FileText, Sparkles } from "lucide-react";

export function EmptyState() {
  const suggestions = [
    "What are the key points in the document?",
    "Summarize the main findings",
    "What does the document say about...?",
    "Compare section A and section B",
  ];
  
  return (
    <div className="flex flex-col items-center justify-center h-full px-4 text-center">
      <div className="w-16 h-16 bg-primary/10 rounded-full flex items-center justify-center mb-6">
        <Sparkles className="h-8 w-8 text-primary" />
      </div>
      
      <h2 className="text-2xl font-bold mb-2">How can I help you?</h2>
      <p className="text-muted-foreground max-w-md mb-8">
        Ask questions about your documents. I'll search through the knowledge base 
        and provide answers with citations.
      </p>
      
      <div className="grid gap-2 w-full max-w-md">
        {suggestions.map((suggestion, index) => (
          <button
            key={index}
            className="text-left px-4 py-3 rounded-lg border bg-card hover:bg-accent transition-colors text-sm"
            onClick={() => {
              // TODO: Dispatch to start conversation with this text
            }}
          >
            {suggestion}
          </button>
        ))}
      </div>
      
      <div className="mt-8 flex items-center gap-2 text-xs text-muted-foreground">
        <FileText className="h-3 w-3" />
        <span>Upload documents in the Admin panel</span>
      </div>
    </div>
  );
}