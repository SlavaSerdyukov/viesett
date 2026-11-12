"""Fixed Python worker, no shell, network calls, filenames or parser diagnostics."""

import resource
import sys

from viesett.document_intelligence.pdf import ExtractionFailure, PdfLimits, extract_text


def main() -> int:
    # Unix is the supported deployment. Parent wall timeout still applies if an
    # OS cannot enforce address-space limits (notably some macOS versions).
    resource.setrlimit(resource.RLIMIT_CPU, (12, 12))
    try:
        resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
    except (OSError, ValueError):
        pass
    limits = PdfLimits(*(int(value) for value in sys.argv[1:5]))
    try:
        result = extract_text(sys.stdin.buffer.read(limits.max_bytes + 1), limits)
        sys.stdout.buffer.write(result.model_dump_json().encode())
        return 0
    except ExtractionFailure as error:
        sys.stdout.write(error.code)
        return 1
    except Exception:
        sys.stdout.write("parser_process_failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
