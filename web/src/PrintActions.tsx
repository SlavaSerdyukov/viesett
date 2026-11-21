import { Link } from "react-router-dom";
import { Printer } from "lucide-react";

export function PrintActions({
  wid,
  notary,
}: {
  wid: string;
  notary: boolean;
}) {
  return (
    <div className="print-tools">
      <div className="print-controls">
        <Link to={`/workspaces/${wid}/overview`}>Back to dossier</Link>
        <Link to={`/workspaces/${wid}/${notary ? "print" : "notary"}`}>
          {notary ? "Print full dossier" : "Prepare for notary"}
        </Link>
        <button className="button" onClick={() => window.print()}>
          <Printer size={16} />
          Print / Save as PDF
        </button>
      </div>
      <p className="print-help">
        For a clean PDF, disable “Headers and footers” in your browser print
        settings.
      </p>
    </div>
  );
}

export function PrintDisclaimer() {
  return (
    <footer className="print-footer">
      Viesett provides automated property and document information assistance.
      Legally significant decisions and binding documents should be reviewed
      with your Belgian notary or another qualified professional.
    </footer>
  );
}
