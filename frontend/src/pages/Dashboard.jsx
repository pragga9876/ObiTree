import { useEffect, useState } from 'react';
import UploadForm from '../components/UploadForm';
import WalletButton from '../components/WalletButton';
import AttestationCard from '../components/AttestationCard';
import { checkHealth } from '../lib/api';

export default function Dashboard() {
  const [apiStatus, setApiStatus] = useState(null);
  const [currentDocument, setCurrentDocument] = useState(null);

  useEffect(() => {
    checkHealth()
      .then((data) => setApiStatus(data))
      .catch((err) => setApiStatus({ status: 'error', message: err.message }));
  }, []);

  const handleUploadSuccess = (data) => {
    setCurrentDocument(data);
  };

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1 className="brand-title">PaperRoots</h1>
        <p className="subtitle">Historical Document Provenance & Attestation on Solana</p>
        <div className="system-status-bar">
          <span
            className={`status-dot ${apiStatus?.status === 'ok' ? 'dot-online' : 'dot-offline'}`}
          ></span>
          <span className="system-status-text">
            FastAPI: {apiStatus?.status === 'ok' ? 'Online' : 'Connecting...'}
            {apiStatus?.database && ` · SQLite: Connected`}
          </span>
        </div>
      </header>

      <main className="dashboard-content">
        <section className="section-card">
          <WalletButton />
        </section>

        <section className="section-card">
          <h3 className="section-title">Upload Historical Document</h3>
          <UploadForm onUploadSuccess={handleUploadSuccess} />
        </section>

        {currentDocument && (
          <section className="section-card attestation-section">
            <AttestationCard documentData={currentDocument} />
          </section>
        )}
      </main>
    </div>
  );
}
