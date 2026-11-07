import { useState, useRef } from 'react';
import { uploadDocument } from '../lib/api';

export default function UploadForm({ onUploadSuccess }) {
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [status, setStatus] = useState(null); // { type: 'success' | 'error' | 'info', message: string }
  const fileInputRef = useRef(null);

  const handleFileChange = (e) => {
    const selected = e.target.files?.[0];
    if (selected) {
      setFile(selected);
      setStatus({
        type: 'info',
        message: `Selected: ${selected.name} (${(selected.size / 1024).toFixed(1)} KB)`,
      });
    }
  };

  const handleSelectClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
      fileInputRef.current.click();
    }
  };

  const handleUpload = async () => {
    if (!file) {
      setStatus({
        type: 'error',
        message: 'Please select a document first.',
      });
      return;
    }

    setUploading(true);
    setStatus({
      type: 'info',
      message: 'Uploading document to server...',
    });

    try {
      const data = await uploadDocument(file);
      setStatus({
        type: 'success',
        message: data?.message || 'Document uploaded successfully!',
      });
      if (onUploadSuccess) {
        onUploadSuccess(data);
      }
    } catch (err) {
      setStatus({
        type: 'error',
        message: err?.message || 'Failed to upload document.',
      });
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="upload-container">
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,image/*,application/pdf,image/png,image/jpeg,image/webp"
        onChange={handleFileChange}
        style={{ display: 'none' }}
        data-testid="file-input"
      />

      <div className="button-group">
        <button
          type="button"
          className="btn btn-outline"
          onClick={handleSelectClick}
          disabled={uploading}
        >
          Select document
        </button>

        <button
          type="button"
          className="btn btn-primary"
          onClick={handleUpload}
          disabled={!file || uploading}
        >
          {uploading ? 'Uploading...' : 'Upload Document'}
        </button>
      </div>

      {file && (
        <div className="selected-file-preview">
          <span className="file-icon">📄</span>
          <span className="file-name">{file.name}</span>
          <span className="file-size">({(file.size / 1024).toFixed(1)} KB)</span>
        </div>
      )}

      {status && (
        <div className={`status-badge status-${status.type}`}>
          {status.message}
        </div>
      )}
    </div>
  );
}
