import React, { useEffect, useState } from "react";
import AdminDocuments from "./AdminDocuments";

function App() {
  const [status, setStatus] = useState("Loading...");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/health")
      .then((res) => res.json())
      .then((data) => setStatus(data.status))
      .catch(() => setStatus("Error connecting to backend"));
  }, []);

  return (
    <div style={{ padding: "20px" }}>
      <h1>DocVault AI — Admin Dashboard</h1>
      <p>Backend status: {status}</p>

      {/* Admin Documents Section */}
      <section style={{ marginTop: "40px" }}>
        <h2>Document Ingestion Admin</h2>
        <AdminDocuments />
      </section>
    </div>
  );
}

export default App;
