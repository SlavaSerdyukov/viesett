import { Link } from "react-router-dom";
import { useAccess } from "./access";
import { Brand } from "./components";
export function ConnectScreen() {
  const access = useAccess();
  return (
    <main id="main" className="start narrow">
      <Brand />
      <h1>Your dossier is private.</h1>
      <p>Reconnect with the access token for this dossier to continue.</p>
      <button className="button" onClick={() => access.request(async () => {})}>
        Connect to dossier
      </button>
      <Link to="/">Back to property check</Link>
    </main>
  );
}
