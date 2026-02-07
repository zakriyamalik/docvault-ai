import React from "react";
import { useGetDLQQuery, useRetryDLQMutation } from "../../app/api/adminApi";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/Card";
import { Button } from "../ui/Button";
import { Badge } from "../ui/Badge";
import { Skeleton } from "../ui/Skeleton";
import { Alert, AlertDescription } from "../ui/Alert";
import { 
  AlertCircle, 
  RefreshCw, 
  RotateCcw, 
  Clock, 
  FileJson,
  AlertTriangle
} from "lucide-react";
import { cn } from "../../lib/utils";

export default function DLQView() {
  const { data: dlqItems = [], isLoading, error, refetch } = useGetDLQQuery();
  const [retry, { isLoading: isRetrying }] = useRetryDLQMutation();

  const handleRetry = async (documentId) => {
    try {
      await retry(documentId).unwrap();
      // Item will disappear from list on next poll
    } catch (err) {
      console.error("Retry failed:", err);
    }
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-48" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-24 w-full" />
          <Skeleton className="h-24 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription className="flex items-center justify-between">
          <span>Error loading DLQ: {error.message}</span>
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
          <AlertCircle className="h-5 w-5 text-destructive" />
          Dead Letter Queue
          {dlqItems.length > 0 && (
            <Badge variant="destructive">{dlqItems.length}</Badge>
          )}
        </CardTitle>
        <Button variant="outline" size="sm" onClick={refetch}>
          <RefreshCw className="h-4 w-4 mr-2" />
          Refresh
        </Button>
      </CardHeader>
      <CardContent>
        {dlqItems.length === 0 ? (
          <div className="text-center py-12">
            <div className="w-16 h-16 bg-green-100 dark:bg-green-900/30 rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="h-8 w-8 text-green-600 dark:text-green-400" />
            </div>
            <h3 className="text-lg font-medium mb-2">All Clear</h3>
            <p className="text-muted-foreground">No failed jobs in the queue</p>
          </div>
        ) : (
          <div className="space-y-4">
            {dlqItems.map((item, index) => (
              <div
                key={item.document_id || index}
                className="border rounded-lg p-4 bg-card hover:bg-accent/50 transition-colors"
              >
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-2">
                    <AlertTriangle className="h-5 w-5 text-destructive" />
                    <span className="font-mono text-sm">
                      {item.document_id?.slice(0, 8)}...
                    </span>
                    <Badge variant="outline" className="text-xs">
                      Failed
                    </Badge>
                  </div>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {item.failed_at 
                      ? new Date(item.failed_at).toLocaleString() 
                      : "Unknown time"}
                  </div>
                </div>
                
                {item.error_snippet && (
                  <div className="mb-3 p-3 bg-destructive/10 rounded-md">
                    <p className="text-sm text-destructive font-mono">
                      {item.error_snippet}
                    </p>
                  </div>
                )}
                
                <div className="flex items-center justify-between">
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex items-center gap-1"
                    onClick={() => {
                      // Toggle payload visibility
                    }}
                  >
                    <FileJson className="h-3 w-3" />
                    View Payload
                  </Button>
                  
                  <Button
                    onClick={() => handleRetry(item.document_id)}
                    disabled={isRetrying}
                    className="flex items-center gap-1"
                  >
                    {isRetrying ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <RotateCcw className="h-3 w-3" />
                    )}
                    Retry Job
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// Missing import
import { CheckCircle2, Loader2 } from "lucide-react";