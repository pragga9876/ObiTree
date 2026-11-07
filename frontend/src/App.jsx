import SolanaWalletProvider from './components/SolanaWalletProvider';
import Dashboard from './pages/Dashboard';
import './App.css';

function App() {
  return (
    <SolanaWalletProvider>
      <div className="app-container">
        <Dashboard />
      </div>
    </SolanaWalletProvider>
  );
}

export default App;
