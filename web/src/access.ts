import { createContext, useContext } from "react";
export type Access = {
  connected: boolean;
  working: boolean;
  connect: (token: string) => void;
  disconnect: () => void;
  request: (action: () => Promise<void>) => void;
  uploads: (action: () => Promise<void>) => void;
};
export const AccessContext = createContext<Access>(null!);
export function useAccess() {
  return useContext(AccessContext);
}
