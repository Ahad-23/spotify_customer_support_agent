import { Link, Route, Routes } from "react-router-dom";
import AgentDashboard from "./pages/AgentDashboard";
import CustomerChat from "./pages/CustomerChat";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<CustomerChat />} />
      <Route path="/agent" element={<AgentDashboard />} />
      <Route
        path="*"
        element={
          <div className="flex min-h-screen flex-col items-center justify-center gap-4">
            <p className="text-neutral-500">Page not found</p>
            <Link to="/" className="text-sm text-blue-600 hover:underline">
              Go to support chat
            </Link>
          </div>
        }
      />
    </Routes>
  );
}
