import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { privatePdf } from "../api";
import { Brand, ErrorMessage, Busy } from "../components";
export function PdfViewer() {
  const { id = "", documentId = "" } = useParams(),
    [params] = useSearchParams(),
    [url, setUrl] = useState<string | null>(null),
    [error, setError] = useState<unknown>(null);
  const page = Math.min(500, Math.max(1, Number(params.get("page")) || 1));
  useEffect(() => {
    let active = true,
      objectUrl: string | null = null;
    const controller = new AbortController();
    void privatePdf(id, documentId, controller.signal)
      .then((value) => {
        objectUrl = value;
        if (active) setUrl(value);
        else URL.revokeObjectURL(value);
      })
      .catch((e) => {
        if (active) setError(e);
      });
    return () => {
      active = false;
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id, documentId]);
  return (
    <main id="main" className="pdf-view">
      <header>
        <Brand />
        <Link to={`/workspaces/${id}/documents`}>Back to documents</Link>
        <span>Target page {page}</span>
        {url && (
          <a
            className="button secondary"
            href={url}
            download="property-document.pdf"
          >
            Download PDF
          </a>
        )}
      </header>
      <ErrorMessage error={error} />
      {url ? (
        <iframe
          title={`Private document · target page ${page}`}
          src={`${url}#page=${page}`}
        />
      ) : (
        !error && <Busy>Opening private document…</Busy>
      )}
      <p className="small muted">
        Target page {page}. Page navigation depends on your browser's PDF
        viewer. No text highlighting is claimed.
      </p>
    </main>
  );
}
