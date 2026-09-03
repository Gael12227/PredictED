import React from "react";
import ReactDOM from "react-dom/client";
import { createBrowserRouter, RouterProvider } from "react-router-dom";
import "./styles.css";
import { SocketProvider } from "./lib/ws";
import { Layout } from "./components/Layout";
import { HomePage } from "./pages/HomePage";
import { ContextPage } from "./pages/ContextPage";

const router = createBrowserRouter([
  {
    path: "/",
    element: <Layout />,
    children: [
      { index: true, element: <HomePage /> },
      { path: "urban", element: <ContextPage context="urban" /> },
      { path: "rural", element: <ContextPage context="rural" /> },
    ],
  },
]);

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <SocketProvider>
      <RouterProvider router={router} />
    </SocketProvider>
  </React.StrictMode>
);
