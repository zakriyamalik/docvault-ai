import React from 'react'; 
import { createBrowserRouter } from "react-router-dom";
import RootLayout from "./components/layout/RootLayout";
import ChatPage from "./pages/ChatPage";
import AdminPage from "./pages/AdminPage";
import DocumentViewerPage from "./pages/DocumentViewerPage";
import ErrorPage from "./pages/ErrorPage";

// const isAdmin = import.meta.env.VITE_IS_ADMIN === "true";

// const router = createBrowserRouter([
//   {
//     path: "/",
//     element: <RootLayout />,
//     errorElement: <ErrorPage />,
//     children: [
//       {
//         index: true,
//         element: <ChatPage />,
//       },
//       {
//         path: "chat",
//         element: <ChatPage />,
//       },
//       {
//         path: "chat/:conversationId",
//         element: <ChatPage />,
//       },
//       ...(isAdmin
//         ? [
//            {
//               path: "admin/documents/:documentId/view",
//               element: <DocumentViewerPage />,
//             },
//             {
//               path: "admin/*",
//               element: <AdminPage />,
//             },
//           ]
//         : []),
//     ],
//   },
// ]);
const isAdmin = true; // Hardcode for now

const router = createBrowserRouter([
  {
    path: "/",
    element: <RootLayout />,
    errorElement: <ErrorPage />,
    children: [
      {
        index: true,
        element: <ChatPage />,
      },
      {
        path: "chat",
        element: <ChatPage />,
      },
      {
        path: "chat/:conversationId",
        element: <ChatPage />,
      },
      ...(isAdmin
        ? [
            {
              path: "admin/documents/:documentId/view", // Specific first
              element: <DocumentViewerPage />,
            },
            {
              path: "admin/*", // Wildcard second
              element: <AdminPage />,
            },
          ]
        : []),
    ],
  },
]);
export default router;