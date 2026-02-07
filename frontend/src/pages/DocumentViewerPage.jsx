import React, { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useGetDocumentChunksQuery } from "../app/api/documentsApi";
import { Card, CardContent, CardHeader, CardTitle } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { Badge } from "../components/ui/Badge";
import { ScrollArea } from "../components/ui/ScrollArea";
import { Skeleton } from "../components/ui/Skeleton";
import { Alert, AlertDescription } from "../components/ui/Alert";
import { 
  ArrowLeft, 
  FileText, 
  Hash, 
  ChevronLeft, 
  ChevronRight,
  Highlighter
} from "lucide-react";
import { cn } from "../lib/utils";

export default function DocumentViewerPage() {
  const { documentId } = useParams();
  const [highlightedChunk, setHighlightedChunk] = useState(null);
  
  const { 
    data: chunks = [], 
    isLoading, 
    error 
  } = useGetDocumentChunksQuery(documentId);

  // Get chunk index from URL query param
  React.useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const chunkId = params.get("chunk");
    if (chunkId && chunks.length > 0) {
      const index = chunks.findIndex((c) => c.id === chunkId);
      if (index !== -1) {
        setHighlightedChunk(index);
        // Scroll to element
        setTimeout(() => {
          document.getElementById(`chunk-${index}`)?.scrollIntoView({
            behavior: "smooth",
            block: "center",
          });
        }, 100);
      }
    }
  }, [chunks]);

  if (isLoading) {
    return (
      <div className="container mx-auto py-8 px-4">
        <Skeleton className="h-8 w-64 mb-4" />
        <Card>
          <CardContent className="space-y-4 py-8">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-32 w-full" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (error) {
    return (
      <div className="container mx-auto py-8 px-4">
        <Alert variant="destructive">
          <AlertDescription>
            Error loading document: {error.message}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Button variant="outline" size="sm" asChild>
              <Link to="/admin">
                <ArrowLeft className="h-4 w-4 mr-2" />
                Back to Admin
              </Link>
            </Button>
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 text-primary" />
              <h1 className="text-xl font-bold">Document Viewer</h1>
            </div>
          </div>
          <Badge variant="outline">
            {chunks.length} chunks
          </Badge>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-sm text-muted-foreground font-normal">
              <span className="font-mono">ID: {documentId}</span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {chunks.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No chunks found for this document</p>
              </div>
            ) : (
              <ScrollArea className="h-[calc(100vh-300px)]">
                <div className="space-y-4">
                  {chunks.map((chunk, index) => (
                    <div
                      key={chunk.id}
                      id={`chunk-${index}`}
                      className={cn(
                        "p-4 rounded-lg border transition-colors",
                        highlightedChunk === index
                          ? "bg-primary/10 border-primary ring-2 ring-primary"
                          : "bg-card hover:bg-accent/50"
                      )}
                    >
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Hash className="h-4 w-4 text-muted-foreground" />
                          <span className="text-sm font-medium">
                            Chunk {chunk.chunk_index}
                          </span>
                          {highlightedChunk === index && (
                            <Badge className="bg-primary text-primary-foreground">
                              <Highlighter className="h-3 w-3 mr-1" />
                              Cited
                            </Badge>
                          )}
                        </div>
                        <span className="text-xs text-muted-foreground font-mono">
                          {chunk.id.slice(0, 8)}...
                        </span>
                      </div>
                      <p className="text-sm leading-relaxed text-foreground">
                        {chunk.preview}
                      </p>
                      <div className="mt-2 text-xs text-muted-foreground">
                        Characters: {chunk.char_start} - {chunk.char_end}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            )}
          </CardContent>
        </Card>
      </main>
    </div>
  );
}