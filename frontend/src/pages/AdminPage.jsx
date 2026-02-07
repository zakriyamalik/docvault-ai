import React from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { AdminLayout } from "../components/admin/AdminLayout";
import AdminDocuments from "../components/admin/AdminDocuments";
import DLQView from "../components/admin/DLQView";

export default function AdminPage() {
  return (
    <AdminLayout>
      <Routes>
        <Route path="/" element={<AdminDocuments />} />
        <Route path="/dlq" element={<DLQView />} />
        <Route path="*" element={<Navigate to="/admin" replace />} />
      </Routes>
    </AdminLayout>
  );
}