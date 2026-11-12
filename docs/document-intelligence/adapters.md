# Deterministic adapters, version 1.0.0

Classifier `signals:1.0.0`: distinct heading weight 0.6, issuer marker 0.2, characteristic field vocabulary 0.2. Acceptance requires score >=0.8, at least two signals and exactly one family heading. UNKNOWN is retained for weak or mixed packets. Signals and confidence are returned even when the prediction is UNKNOWN. A manual correction records a new generation without replacing the automatic prediction.

Adapters parse explicit labeled Dutch fields and narrowly recognized statements. They support next-line label values, conservative date formats (ISO or day/month/year), decimal commas and exact standardized identifiers. They do not use a language model or general layout inference. Conflicting singleton values are omitted; repeated parcels, actions, investigation references and violations remain separate. At most 300 fields are allowed; an excess fails explicitly rather than truncating facts. Text offsets refer to the retained normalized page. No missing field is converted into a guessed favorable outcome.

| Adapter | Explicit supported fields |
| --- | --- |
| `epc:1.0.0` | Certificate/reference code, labeled property address/box, issue and printed end dates, EPC label, bounded numeric kWh/m²/year score, explicit residential designation |
| `asbestos:1.0.0` | Attest/reference code, address/box, issue/end dates, asbestveilig/niet-asbestveilig conclusion, explicit material count, structured management/removal action lines, private/common/common-used scope |
| `electrical:1.0.0` | Inspection body, reference, installation address/box, inspection date/type, explicit conforming/non-conforming conclusion, structured infringement and follow-up lines |
| `soil:1.0.0` | Reference/date, cadastral division, section, parcel numbers, all explicit normalized CaPaKeys, GIR statement/recorded flag, explicit risk-ground statement, labeled soil conclusion, investigation references/advice |

An absent asbestos scope is typed UNSPECIFIED; it cannot prove private/common-part coverage. A missing validity end date is UNVERIFIED. Document presence is separate from validity and does not authenticate a signature or check an OVAM/VEKA registry. No ten-year asbestos or EPC expiry is silently synthesized. No-GIR wording means absence of recorded information, never uncontaminated soil.

EPC scores can be negative and use printed units such as `kWh/(m².jaar)`. These are preserved numerically; an absent label is never calculated from a score. The official [VEKA explanation](https://www.vlaanderen.be/bouwen-wonen-en-energie/energieprestatiecertificaten-epcs/epc-van-een-residentiele-gebouweenheid/uitleg-bij-het-epc-res?language=nl) explicitly warns that its score-to-label table is indicative rather than a replacement for the certificate's actual label.

Supported fixtures are generated small PDFs from `tests/document_fixtures.py`: fictional Teststraat identities and SYNTHETIC reference numbers. No customer documents or copied official PDF contents are committed. All four were rendered locally with macOS `sips` and inspected; this QA tool is not a runtime/CI dependency. Normal CI needs only Python and PostgreSQL.

Intentionally unsupported: image-only/mixed scans without usable text, encrypted PDFs, packet splitting, handwriting, signature validation, graphical-only EPC selection arrows, arbitrary electrical drawings, full asbestos inventories, irregular tables, multilingual template coverage, old cadastral notations without an explicit unambiguous CaPaKey, unlabeled/multicolumn addresses and automatic certificate authenticity checks. Such fields remain absent, documents UNKNOWN/OCR_REQUIRED, or checks require review. Production compatibility with a broad representative corpus remains unverified; synthetic correctness is not measured real-world extraction accuracy.
