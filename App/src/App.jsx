import {
  BrowserRouter as Router,
  Routes,
  Route,
  Navigate,
} from "react-router-dom";

import Chatbot from "./Chatbot";
import UploadPage from "./UploadPage";

export default function App() {
  return (
    <Router>
      <Routes>
        <Route path="/" element={<Navigate to="/upload" replace />} />
        <Route path="/upload" element={<UploadPage />} />
        <Route path="/ask" element={<Chatbot />} />
      </Routes>
    </Router>
  );
}
