import { useEffect, useMemo, useRef, useState } from "react";
import { useWallet } from "@solana/wallet-adapter-react";
import { uploadDocument } from "../lib/api";

const PHASES = [
  "Reading the clipping…",
  "Transcribing the notice…",
  "Extracting family relationships…",
  "Building the structured record…",
  "Computing the document hash…",
  "Computing the canonical record hash…",
];

function fileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function UploadClipping({ projectId = null, onSuccess, title, subtitle }) {
  const { publicKey } = useWallet();
  const [file, setFile] = useState(null);
  const [dragging, setDragging] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [phase, setPhase] = useState(0);
  const [error, setError] = useState(null);
  const inputRef = useRef(null);

  const previewUrl = useMemo(() => {
    if (!file || !file.type?.startsWith("image/")) return null;
    return URL.createObjectURL(file);
  }, [file]);

  useEffect(() => {
    if (!previewUrl) return undefined;
    return () => URL.revokeObjectURL(previewUrl);
  }, [previewUrl]);

  useEffect(() => {
    if (!uploading) return undefined;
    const timer = window.setInterval(() => {
      setPhase((current) => (current + 1) % PHASES.length);
    }, 4200);
    return () => window.clearInterval(timer);
  }, [uploading]);

  const pickFile = (selected) => {
    if (!selected) return;
    setFile(selected);
    setError(null);
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    pickFile(event.dataTransfer.files?.[0]);
  };

  const handleUpload = async () => {
    if (!file || uploading) return;
    setPhase(0);
    setUploading(true);
    setError(null);
    try {
      const data = await uploadDocument(file, {
        projectId,
        wallet: publicKey?.toBase58(),
      });
      setFile(null);
      if (inputRef.current) inputRef.current.value = "";
      onSuccess?.(data);
    } catch (err) {
      setError(err?.message || "The clipping could not be processed.");
    } finally {
      setUploading(false);
      setPhase(0);
    }
  };

  return (
    <div className={`upload-clipping ${projectId ? "upload-clipping-inline" : ""}`}>
      <div className="upload-heading">
        <span className="kicker">{projectId ? "Add another clipping" : "New family record"}</span>
        <h3>{title || (projectId ? "Upload a second page" : "Upload an obituary")}</h3>
        <p>
          {subtitle ||
            "Upload and extraction do not require a wallet. You can review the scan against the extracted record first; connecting a wallet is only needed to attest."}
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".pdf,image/*,application/pdf,image/png,image/jpeg,image/webp"
        onChange={(event) => pickFile(event.target.files?.[0])}
        hidden
        data-testid="file-input"
      />

      <button
        type="button"
        className={`dropzone ${dragging ? "is-dragging" : ""} ${file ? "has-file" : ""}`}
        onClick={() => inputRef.current?.click()}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        disabled={uploading}
      >
        {previewUrl ? (
          <span className="dropzone-preview">
            <img src={previewUrl} alt="Selected clipping preview" />
            <span className="dropzone-preview-caption">
              <span className="dropzone-file">{file.name}</span>
              <span className="dropzone-meta">{fileSize(file.size)} · ready to read</span>
            </span>
          </span>
        ) : (
          <>
            <span className="dropzone-title">Drop the clipping here</span>
            <span className="dropzone-meta">or click to browse · JPG, PNG, WEBP or PDF</span>
            {file && (
              <span className="dropzone-file">
                {file.name} · {fileSize(file.size)}
              </span>
            )}
          </>
        )}
      </button>

      {error && <div className="notice notice-error">{error}</div>}

      {uploading ? (
        <div className="upload-progress" role="status" aria-live="polite">
          <span className="upload-progress-bar" />
          <span className="upload-progress-text">{PHASES[phase]}</span>
          <span className="upload-progress-note">This can take a minute.</span>
        </div>
      ) : (
        <div className="upload-actions">
          <button
            type="button"
            className="btn btn-ink btn-lg"
            onClick={handleUpload}
            disabled={!file}
          >
            {projectId ? "Extract & add to record" : "Extract the record"}
          </button>
          <span className="upload-wallet-note">
            {publicKey
              ? "Your wallet is recorded as the uploader. Attestation is a separate step."
              : "No wallet connected. You can still upload and inspect the extracted record."}
          </span>
        </div>
      )}
    </div>
  );
}
