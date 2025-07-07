import { useState, useEffect, useRef } from "react";
import "./chatbot.css";

export default function Chatbot() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [files, setFiles] = useState([]);
  const [uploading, setUploading] = useState(false);
  const chatBoxRef = useRef(null);

  const refreshFiles = async () => {
    try {
      const res = await fetch("http://localhost:8000/files");
      if (!res.ok) throw new Error("No /files route");
      const data = await res.json();
      const merged = (data.files || []).map((f) => ({
        name: f,
        active: (data.active || []).includes(f),
      }));
      setFiles(merged);
    } catch (err) {
      console.error("Failed to fetch files:", err.message);
      setFiles([]);
    }
  };

  useEffect(() => {
    refreshFiles();
  }, []);

  const handleUpload = async (e) => {
    const file = e.target.files[0];
    if (!file || files.length >= 5) return;

    setUploading(true);

    const fd = new FormData();
    fd.append("pdf", file);

    try {
      const res = await fetch("http://localhost:8000/upload", {
        method: "POST",
        body: fd,
      });

      const data = await res.json();

      if (res.ok && !data.error) {
        await refreshFiles();
      } else {
        alert(data.error || "Failed to upload PDF.");
      }
    } catch {
      alert("Upload failed. Backend unreachable.");
    } finally {
      setUploading(false);
    }
  };

  const toggle = async (fname, on) => {
    try {
      await fetch("http://localhost:8000/toggle", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: fname, active: on }),
      });
      refreshFiles();
    } catch {
      alert("Toggle failed. Backend unreachable.");
    }
  };

  const askQuestion = async () => {
    if (!question.trim()) return;

    setMessages((p) => [...p, { role: "user", text: question }]);
    setQuestion("");

    const selected = files.filter((f) => f.active).map((f) => f.name);

    try {
      const res = await fetch("http://localhost:8000/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, selected_files: selected }),
      });
      const data = await res.json();
      setMessages((p) => [
        ...p,
        { role: "bot", text: data.answer || data.error },
      ]);
    } catch {
      setMessages((p) => [
        ...p,
        { role: "bot", text: "Error: backend unreachable." },
      ]);
    }
  };

  useEffect(() => {
    if (chatBoxRef.current)
      chatBoxRef.current.scrollTop = chatBoxRef.current.scrollHeight;
  }, [messages]);

  return (
    <div className="app-row">
      {/* Sidebar */}
      <div className="sidebar">
        <div className="sidebar-header">
          <span>PDFs ({files.length}/5)</span>
          <label htmlFor="addFile" className="add-file-btn">
            Add File
          </label>
          <input
            id="addFile"
            type="file"
            accept="application/pdf"
            style={{ display: "none" }}
            onChange={handleUpload}
            disabled={files.length >= 5}
          />
        </div>

        {files.map(({ name, active }) => (
          <label key={name} className="file-item">
            {name}
            <input
              type="checkbox"
              checked={active}
              onChange={(e) => toggle(name, e.target.checked)}
            />
          </label>
        ))}
      </div>

      {/* Main Chat Panel */}
      <div className="main-panel">
        <div className="chat-wrapper">
          <h2 className="chat-heading">PDF Chatbot</h2>

          <div className="chat-container">
            <div className="chat-box" ref={chatBoxRef}>
              {messages.map((m, i) => (
                <div key={i} className={`message ${m.role}`}>
                  {m.role === "bot" ? (
                    <div className="formatted-response">{m.text}</div>
                  ) : (
                    m.text
                  )}
                </div>
              ))}
            </div>

            <div className="input-container">
              <input
                type="text"
                className="user-input"
                placeholder="Ask something..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && askQuestion()}
              />
              <button className="sendBtn" onClick={askQuestion}>
                Send
              </button>
            </div>
          </div>
        </div>
      </div>

      {uploading && (
        <div className="upload-overlay">
          <div className="upload-box">
            <p>Uploading PDF...</p>
          </div>
        </div>
      )}
    </div>
  );
}
