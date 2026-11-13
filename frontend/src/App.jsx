import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import Layout from "./components/Layout.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import Forgot from "./pages/Forgot.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import Vendors from "./pages/Vendors.jsx";
import RFQs from "./pages/RFQs.jsx";
import RFQForm from "./pages/RFQForm.jsx";
import RFQDetail from "./pages/RFQDetail.jsx";
import Compare from "./pages/Compare.jsx";
import MyRFQs from "./pages/MyRFQs.jsx";
import MyRFQDetail from "./pages/MyRFQDetail.jsx";
import Approvals from "./pages/Approvals.jsx";
import ApprovalDetail from "./pages/ApprovalDetail.jsx";
import PurchaseOrders from "./pages/PurchaseOrders.jsx";
import PurchaseOrderDetail from "./pages/PurchaseOrderDetail.jsx";
import Invoices from "./pages/Invoices.jsx";
import InvoiceDetail from "./pages/InvoiceDetail.jsx";
import Notifications from "./pages/Notifications.jsx";
import Activity from "./pages/Activity.jsx";
import Reports from "./pages/Reports.jsx";

const STAFF = ["admin", "manager", "procurement_officer"];

function Protected({ children, roles }) {
  const { user, loading } = useAuth();
  if (loading) return <p className="center">Loading...</p>;
  if (!user) return <Navigate to="/login" replace />;
  if (roles && !roles.includes(user.role)) return <Navigate to="/" replace />;
  return <Layout>{children}</Layout>;
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/register" element={<Register />} />
      <Route path="/forgot-password" element={<Forgot />} />
      <Route path="/" element={<Protected><Dashboard /></Protected>} />
      <Route path="/vendors" element={<Protected roles={STAFF}><Vendors /></Protected>} />
      <Route path="/rfqs" element={<Protected roles={STAFF}><RFQs /></Protected>} />
      <Route path="/rfqs/new" element={<Protected roles={STAFF}><RFQForm /></Protected>} />
      <Route path="/rfqs/:id" element={<Protected roles={STAFF}><RFQDetail /></Protected>} />
      <Route path="/rfqs/:id/compare" element={<Protected roles={STAFF}><Compare /></Protected>} />
      <Route path="/my-rfqs" element={<Protected roles={["vendor"]}><MyRFQs /></Protected>} />
      <Route path="/my-rfqs/:id" element={<Protected roles={["vendor"]}><MyRFQDetail /></Protected>} />
      <Route path="/approvals" element={<Protected roles={STAFF}><Approvals /></Protected>} />
      <Route path="/approvals/:id" element={<Protected roles={STAFF}><ApprovalDetail /></Protected>} />
      <Route path="/purchase-orders" element={<Protected><PurchaseOrders /></Protected>} />
      <Route path="/purchase-orders/:id" element={<Protected><PurchaseOrderDetail /></Protected>} />
      <Route path="/invoices" element={<Protected><Invoices /></Protected>} />
      <Route path="/invoices/:id" element={<Protected><InvoiceDetail /></Protected>} />
      <Route path="/notifications" element={<Protected><Notifications /></Protected>} />
      <Route path="/activity" element={<Protected roles={STAFF}><Activity /></Protected>} />
      <Route path="/reports" element={<Protected roles={STAFF}><Reports /></Protected>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}