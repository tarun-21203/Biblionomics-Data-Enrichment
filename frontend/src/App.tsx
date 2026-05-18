import { BrowserRouter, Routes, Route } from "react-router-dom";
import Layout from "./components/Layout";
import Dashboard from "./pages/Dashboard";
import Submit from "./pages/Submit";
import EnrichmentDetail from "./pages/EnrichmentDetail";

export default function App() {
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/submit" element={<Submit />} />
          <Route path="/enrichment/:id" element={<EnrichmentDetail />} />
        </Routes>
      </Layout>
    </BrowserRouter>
  );
}