import { createContext, useContext } from "react";

export const WalletStatusContext = createContext({ error: null, clearError: () => {} });

export function useWalletStatus() {
  return useContext(WalletStatusContext);
}
