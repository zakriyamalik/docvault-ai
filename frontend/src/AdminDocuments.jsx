import React, { useEffect, useState } from "react";
const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

export default function AdminDocuments() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch(`${API_URL}/api/v1/documents`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch documents");
        return res.json();
      })
      .then((data) => {
        setDocuments(data);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  if (loading) return <p>Loading documents...</p>;
  if (error) return <p style={{ color: "red" }}>Error: {error}</p>;

  return (
    <div>
      {documents.length === 0 ? (
        <p>No documents found.</p>
      ) : (
        <table border="1" cellPadding="5" cellSpacing="0">
          <thead>
            <tr>
              <th>ID</th>
              <th>Filename</th>
              <th>Status</th>
              <th>Chunks Count</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {documents.map((doc) => {
              // Parse meta_json safely
              let meta = {};
              try {
                meta = typeof doc.meta_json === "string" ? JSON.parse(doc.meta_json) : doc.meta_json;
              } catch {}

              const chunksCount = meta?.chunks_count || 0;

              return (
                <tr key={doc.id}>
                  <td>{doc.id}</td>
                  <td>{doc.filename}</td>
                  <td>{doc.status}</td>
                  <td>{chunksCount}</td>
                  <td>
                    <a
                      href={`${API_URL}/api/v1/documents/${doc.id}/status`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Status
                    </a>{" "}
                    |{" "}
                    <a
                      href={`${API_URL}/api/v1/documents/${doc.id}/chunks`}
                      target="_blank"
                      rel="noopener noreferrer"
                    >
                      Chunks
                    </a>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      )}
    </div>
  );
}
