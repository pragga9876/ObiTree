import { useEffect, useState } from 'react';
import UploadForm from '../components/UploadForm';
import WalletButton from '../components/WalletButton';
import { checkHealth } from '../lib/api';

export default function Dashboard() {
  const [apiStatus, setApiStatus] = useState(null);

  useEffect(() => {
    checkHealth()
      .then((data) => setApiStatus(data))
      .catch((err) => setApiStatus({ status: 'error', message: err.message }));
  }, []);

  return (
    <div className="dashboard-container">
      <header className="dashboard-header">
        <h1 className="brand-title">PaperRoots</h1>
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
          <UploadForm />
        </section>

        <section className="section-card">
          <WalletButton />
        </section>
      </main>
    </div>
  );
}
