import React from "react";
import { BrowserRouter as Router, Routes, Route } from "react-router-dom";
import Menu from "./pages/Menu";
import OrderComplete from "./pages/OrderComplete";
import Admin from "./pages/Admin";
import Display from "./pages/Display";
import Login from "./pages/Login";
import { CartProvider } from "./context/CartContext";
import { AuthProvider } from "./context/AuthContext";
import ProtectedRoute from "./components/ProtectedRoute";

export default function App() {
  return (
    <AuthProvider>
      <CartProvider>
        <Router basename={import.meta.env.BASE_URL}>
          <Routes>
            <Route path="/" element={<Login />} />

            <Route
              path="/menu"
              element={
                <ProtectedRoute>
                  <Menu />
                </ProtectedRoute>
              }
            />
            <Route path="/order-complete" element={<OrderComplete />} />
            <Route
              path="/admin"
              element={
                <ProtectedRoute>
                  <Admin />
                </ProtectedRoute>
              }
            />
            <Route
              path="/display"
              element={
                <ProtectedRoute>
                  <Display />
                </ProtectedRoute>
              }
            />
          </Routes>
        </Router>
      </CartProvider>
    </AuthProvider>
  );
}
