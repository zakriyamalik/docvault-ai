import React, { useState } from "react";
import { 
  useListDocumentsQuery, 
  useReembedDocumentMutation 
} from "../../app/api/documentsApi";
import { useDocumentStatusPolling } from "../../hooks/useDocumentStatusPolling";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/Card";
import { Skeleton } from "../ui/Skeleton";
import { Alert, AlertDescription } from "../ui/Alert";
import { 
  Loader2, 
  RefreshCw, 
  FileText, 
  RotateCcw, 
  CheckCircle2, 
  AlertCircle,
  Clock,
  Eye
} from "lucide-react";
import { cn } from "../../lib/utils";
import { Link } from "react-router-dom";

function DocumentRow({ doc }) {
  const { status, chunksCount, isPolling } = useDocumentStatusPolling(doc.id, doc.status);
  const [reembed, { isLoading: isReembedding }] = useReembedDocumentMutation();

  const handleReembed = async () => {
    try {
      await reembed(doc.id).unwrap();
    } catch (err) {
      console.error("Re-embed failed:", err);
    }
  };

  const getStatusConfig = (s) => {
    switch (s) {
      case "completed":
        return { 
          color: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200", 
          icon: CheckCircle2,
          label: "Completed"
        };
      case "processing":
        return { 
          color: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200", 
          icon: Loader2,
          label: "Processing"
        };
      case "queued":
        return { 
          color: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200", 
          icon: Clock,
          label: "Queued"
        };
      case "failed":
        return { 
          color: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200", 
          icon: AlertCircle,
          label: "Failed"
        };
      default:
        return { 
          color: "bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-200", 
          icon: FileText,
          label: s
        };
    }
  };

  const config = getStatusConfig(status);
  const StatusIcon = config.icon;

  return (
    <tr className="border-b last:border-0 hover:bg-muted/50 transition-colors">
      <td className="py-4 px-4">
        <div className="flex items-center gap-3">
          <FileText className="h-4 w-4 text-muted-foreground" />
          <span className="font-medium truncate max-w-[200px]" title={doc.filename}>
            {doc.filename}
          </span>
        </div>
      </td>
      <td className="py-4 px-4">
        <Badge className={cn(config.color, "flex items-center gap-1 w-fit")}>
          <StatusIcon className={cn("h-3 w-3", status === "processing" && "animate-spin")} />
          {config.label}
          {isPolling && <span className="ml-1 text-[10px]">(polling)</span>}
        </Badge>
      </td>
      <td className="py-4 px-4 text-muted-foreground">
        {chunksCount !== undefined ? chunksCount : doc.chunks_count || 0}
      </td>
      <td className="py-4 px-4">
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleReembed}
            disabled={isReembedding || status === "processing" || status === "queued"}
            className="flex items-center gap-1"
          >
            {isReembedding ? (
              <Loader2 className="h-3 w-3 animate-spin" />
            ) : (
              <RotateCcw className="h-3 w-3" />
            )}
            Re-embed
          </Button>
          
          <Button variant="ghost" size="sm" asChild>
            <Link 
              to={`/admin/documents/${doc.id}/view`}
              className="flex items-center gap-1"
            >
              <Eye className="h-3 w-3" />
              View
            </Link>
          </Button>
        </div>
      </td>
    </tr>
  );
}

export default function AdminDocuments() {
  const { data: documents = [], isLoading, error, refetch } = useListDocumentsQuery();
  const [filter, setFilter] = useState("all");

  const filteredDocs = documents.filter((doc) => {
    if (filter === "all") return true;
    return doc.status === filter;
  });

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between">
          <span>Error loading documents: {error.message}</span>
          <Button variant="outline" size="sm" onClick={refetch}>
            Retry
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle className="flex items-center gap-2">
          <FileText className="h-5 w-5" />
          Documents ({documents.length})
        </CardTitle>
        <div className="flex items-center gap-2">
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          >
            <option value="all">All Status</option>
            <option value="completed">Completed</option>
            <option value="processing">Processing</option>
            <option value="queued">Queued</option>
            <option value="failed">Failed</option>
          </select>
          <Button variant="outline" size="sm" onClick={refetch}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Refresh
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {filteredDocs.length === 0 ? (
          <div className="text-center py-12 text-muted-foreground">
            <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
            <p>No documents found</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b bg-muted/50">
                  <th className="text-left py-3 px-4 font-medium">Filename</th>
                  <th className="text-left py-3 px-4 font-medium">Status</th>
                  <th className="text-left py-3 px-4 font-medium">Chunks</th>
                  <th className="text-left py-3 px-4 font-medium">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredDocs.map((doc) => (
                  <DocumentRow key={doc.id} doc={doc} />
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}