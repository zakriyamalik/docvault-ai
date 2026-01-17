import React, { useEffect, useState } from "react";

function App() {
  const [status, setStatus] = useState("Loading...");

  useEffect(() => {
    fetch("http://127.0.0.1:8000/health")
      .then((res) => res.json())
      .then((data) => setStatus(data.status))
      .catch(() => setStatus("Error connecting to backend"));
  }, []);

  return (
    <div>
      <h1>DocVault AI — Coming Soon</h1>
      <p>Backend status: {status}</p>
    </div>
  );
}

export default App;
