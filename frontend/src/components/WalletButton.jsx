import { useWallet } from '@solana/wallet-adapter-react';
import { useWalletModal } from '@solana/wallet-adapter-react-ui';
import { formatAddress } from '../lib/solana';

export default function WalletButton() {
  const { publicKey, connected, connecting, disconnecting, disconnect } = useWallet();
  const { setVisible } = useWalletModal();

  const handleConnectClick = () => {
    setVisible(true);
  };

  const handleDisconnectClick = async () => {
    try {
      await disconnect();
    } catch (err) {
      console.error('Wallet disconnect error:', err);
    }
  };

  return (
    <div className="wallet-container">
      <div className="wallet-header">
        <h3 className="section-title">Wallet</h3>
        <span className="network-pill">Devnet</span>
      </div>

      {connected && publicKey ? (
        <div className="wallet-connected-box">
          <div className="wallet-info">
            <span className="wallet-indicator"></span>
            <span
              className="wallet-address"
              title={publicKey.toBase58()}
              data-testid="wallet-address"
            >
              {formatAddress(publicKey.toBase58(), 6)}
            </span>
          </div>

          <p className="wallet-full-address">
            <code>{publicKey.toBase58()}</code>
          </p>

          <button
            type="button"
            className="btn btn-outline"
            onClick={handleDisconnectClick}
            disabled={disconnecting}
          >
            {disconnecting ? 'Disconnecting...' : 'Disconnect'}
          </button>
        </div>
      ) : (
        <button
          type="button"
          className="btn btn-primary"
          onClick={handleConnectClick}
          disabled={connecting}
          data-testid="connect-wallet-btn"
        >
          {connecting ? 'Connecting...' : 'Connect Wallet'}
        </button>
      )}
    </div>
  );
}
