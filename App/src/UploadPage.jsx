import { useState } from "react";
import { useNavigate } from "react-router-dom";
import "./chatbot.css";

export default function UploadPage() {
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setLoading(true);

    const fd = new FormData();
    fd.append("pdf", file);

    try {
      const res = await fetch("http://localhost:8000/upload", {
        method: "POST",
        body: fd,
      });

      const data = await res.json();

      if (res.ok && !data.error) {
        navigate("/ask");
      } else {
        alert(data.error || "Failed to upload PDF.");
        setLoading(false);
      }
    } catch {
      alert("Server error while uploading.");
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <h2 className="chat-heading">PDF Chatbot – Upload</h2>

      <div className="upload-section">
        <label htmlFor="pdf-upload" className="upload-label">
          Upload a PDF
        </label>
        <input
          id="pdf-upload"
          type="file"
          accept="application/pdf"
          onChange={handleUpload}
          disabled={loading}
        />
      </div>

      {loading && (
        <div className="upload-overlay">
          <div className="upload-box">
            <p>Uploading PDF...</p>
          </div>
        </div>
      )}
    </div>
  );
}
