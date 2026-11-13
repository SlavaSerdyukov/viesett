import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { privatePdf } from "../api";
import { Brand, ErrorMessage, Busy } from "../components";
export function PdfViewer() {
  const heading = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    heading.current?.focus();
  }, []);
  const { id = "", documentId = "" } = useParams(),
    [params] = useSearchParams(),
    [url, setUrl] = useState<string | null>(null),
    [nativeViewer, setNativeViewer] = useState(true),
    [error, setError] = useState<unknown>(null);
  const page = Math.min(500, Math.max(1, Number(params.get("page")) || 1));
  useEffect(() => {
    setUrl(null);
    setError(null);
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
      <h1 className="sr-only" tabIndex={-1} ref={heading}>
        Private source document
      </h1>
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
      {url && (
        <button
          className="text-button"
          onClick={() => setNativeViewer((shown) => !shown)}
        >
          {nativeViewer ? "Use download instead" : "Show PDF viewer"}
        </button>
      )}
      {url && nativeViewer ? (
        <iframe
          title={`Private document · target page ${page}`}
          src={`${url}#page=${page}`}
          onError={() => setNativeViewer(false)}
        />
      ) : (
        !url && !error && <Busy>Opening private document…</Busy>
      )}
      <p className="small muted">
        Target page {page}. Page navigation depends on your browser's PDF
        viewer. No text highlighting is claimed.
        {url &&
          " If native PDF rendering is unavailable or blank, use Download PDF above. The file has already been fetched through your private session."}
      </p>
    </main>
  );
}
