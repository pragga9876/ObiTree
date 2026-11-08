import WalletButton from "./WalletButton";

export default function Masthead({ route, onHome, onArchive }) {
  return (
    <header className="masthead">
      <div className="masthead-main">
        <button type="button" className="brand-lockup" onClick={onHome} aria-label="ObiTree home">
          <img className="brand-mark" src="/ObiTree_Logo.jpg" alt="ObiTree seal" />
          <span className="brand-type">
            <span className="brand-name">ObiTree</span>
            <span className="brand-tagline">The family record, sealed on Solana</span>
          </span>
        </button>

        <WalletButton />
      </div>

      <nav className="masthead-nav" aria-label="Primary">
        <button
          type="button"
          className={`nav-link ${route.name === "home" ? "is-current" : ""}`}
          onClick={onHome}
        >
          Home
        </button>
        <button type="button" className="nav-link" onClick={onArchive}>
          Archive
        </button>
        <span className="nav-network">
          <span className="dot" />
          Solana Devnet
        </span>
      </nav>
    </header>
  );
}
