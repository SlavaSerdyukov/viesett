import calendar
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from viesett.domain.intelligence import (
    AnalysisKind,
    Applicability,
    AsbestosVariant,
    AssociationStatus,
    ExtractionStatus,
    Presence,
    Requirement,
    RuleMetadata,
)
from viesett.domain.types import Authority, Severity
from viesett.rules.catalog import CATALOG, effective


@dataclass(frozen=True)
class Fact:
    value: str | int | float | bool
    evidence_ids: tuple[UUID, ...]
    authority: Authority = Authority.DOCUMENTED


@dataclass(frozen=True)
class DocumentInput:
    id: UUID
    kind: AnalysisKind
    status: ExtractionStatus
    association: AssociationStatus
    fields: dict[str, tuple[Fact, ...]]
    evidence_ids: tuple[UUID, ...] = ()

    def one(self, key: str) -> Fact | None:
        facts = self.fields.get(key, ())
        return facts[0] if len({str(f.value) for f in facts}) == 1 else None


@dataclass(frozen=True)
class RuleContext:
    evaluation_date: date
    documents: tuple[DocumentInput, ...]
    parcels: frozenset[str] = frozenset()
    facts: dict[str, Fact] = field(default_factory=dict)

    def value(self, key: str, *, allow_unverified: bool = False) -> str | int | float | bool | None:
        fact = self.facts.get(key)
        return (
            fact.value
            if fact and (allow_unverified or fact.authority != Authority.UNVERIFIED)
            else None
        )


@dataclass(frozen=True)
class RuleFinding:
    code: str
    severity: Severity
    summary: str
    details: str
    rule: RuleMetadata
    evidence_ids: tuple[UUID, ...]


@dataclass(frozen=True)
class RuleResult:
    requirements: tuple[Requirement, ...]
    findings: tuple[RuleFinding, ...]


def add_months(value: date, months: int) -> date:
    offset = value.year * 12 + value.month - 1 + months
    year, month = divmod(offset, 12)
    return date(year, month + 1, min(value.day, calendar.monthrange(year, month + 1)[1]))


def evaluate(context: RuleContext) -> RuleResult:
    when = context.evaluation_date
    requirements = []
    findings = []
    active = [
        d
        for d in context.documents
        if d.status == ExtractionStatus.READY and d.association == AssociationStatus.MATCHED
    ]

    def emit(
        code: str,
        severity: Severity,
        summary: str,
        details: str,
        documents: list[DocumentInput] | None = None,
    ) -> None:
        metadata = CATALOG[code]
        if not effective(metadata, when):
            return
        ids = {eid for doc in documents or [] for eid in doc.evidence_ids}
        ids.update(
            eid
            for key, fact in context.facts.items()
            if fact.authority != Authority.UNVERIFIED
            or (code == "FL_EPC_RENOVATION" and key == "transaction.authentic_deed_date")
            for eid in fact.evidence_ids
        )
        findings.append(RuleFinding(code, severity, summary, details, metadata, tuple(sorted(ids))))

    def requirement(
        kind: AnalysisKind,
        code: str,
        applicability: Applicability,
        reason: str,
        variant: AsbestosVariant | None = None,
    ) -> None:
        metadata = CATALOG[code]
        docs = [d for d in context.documents if d.kind == kind]
        if variant:
            docs = [d for d in docs if (v := d.one("variant")) is None or v.value == variant]
        usable = [d for d in docs if d in active]
        missing = []
        presence = Presence.MISSING
        valid = []
        for doc in usable:
            if variant and doc.one("variant") is None:
                continue
            expiry = doc.one("valid_until")
            issued = doc.one("issue_date")
            # Printed issue dates in the future cannot establish current presence.
            if issued and date.fromisoformat(str(issued.value)) > when:
                continue
            if expiry and date.fromisoformat(str(expiry.value)) < when:
                continue
            if (
                kind == AnalysisKind.EPC
                and issued
                and date.fromisoformat(str(issued.value)) < date(2019, 1, 1)
            ):
                continue
            if kind == AnalysisKind.EPC and doc.one("label") is None:
                continue
            if kind == AnalysisKind.ASBESTOS_CERTIFICATE and doc.one("conclusion") is None:
                continue
            if kind == AnalysisKind.ELECTRICAL_INSPECTION and doc.one("conforming") is None:
                continue
            if kind == AnalysisKind.SOIL_CERTIFICATE and not doc.fields.get("parcel.capakey"):
                continue
            valid.append(doc)
        if valid:
            presence = Presence.PRESENT
        elif usable:
            expiry_found = any(
                (e := d.one("valid_until")) and date.fromisoformat(str(e.value)) < when
                for d in usable
            )
            presence = Presence.EXPIRED if expiry_found else Presence.UNUSABLE
        elif any(d.association == AssociationStatus.MISMATCH for d in docs):
            presence = Presence.MISMATCHED
        elif any(d.status == ExtractionStatus.OCR_REQUIRED for d in docs):
            presence = Presence.OCR_REQUIRED
        elif docs:
            presence = Presence.UNUSABLE
        if kind == AnalysisKind.SOIL_CERTIFICATE:
            covered = {str(f.value) for d in valid for f in d.fields.get("parcel.capakey", ())}
            missing = sorted(context.parcels - covered)
            if missing and valid:
                presence = Presence.UNUSABLE
                reason += " Certificates do not demonstrate coverage for every official parcel."
        if when < metadata.effective_from:
            applicability = Applicability.NOT_YET_EFFECTIVE
        elif metadata.effective_to and when > metadata.effective_to:
            applicability = Applicability.UNKNOWN
            reason = "No reviewed rule version covers this evaluation date."
        result = Requirement(
            kind=kind,
            variant=variant,
            rule=metadata,
            applicability=applicability,
            presence=presence,
            validity_status=(
                "EXPIRED"
                if presence == Presence.EXPIRED
                else "EXPLICIT_CURRENT"
                if valid and all(d.one("valid_until") for d in valid)
                else "UNVERIFIED"
            ),
            reason=reason,
            evaluation_date=when,
            evidence_ids=sorted({eid for d in docs for eid in d.evidence_ids}),
            document_ids=[d.id for d in docs],
            missing_parcels=missing,
        )
        requirements.append(result)
        if applicability == Applicability.REQUIRED and presence != Presence.PRESENT:
            emit(
                code,
                Severity.BLOCKING_DATA_GAP,
                f"{kind.value.replace('_', ' ').title()} evidence incomplete",
                (
                    "Viesett lacks reliable evidence for this check; this does not "
                    "establish a legal transaction prohibition. "
                )
                + reason,
                docs,
            )

    residential = context.value("property.residential")
    if residential is None:
        declarations = [
            f for d in active if d.kind == AnalysisKind.EPC if (f := d.one("residential"))
        ]
        if len({str(f.value) for f in declarations}) == 1 and declarations:
            residential = declarations[0].value
    transfer = context.value("transaction.qualifying_transfer")
    epc_exempt = context.value("transaction.epc_exemption")
    epc_app = Applicability.CONDITIONAL
    if residential is True and transfer is True and epc_exempt is False:
        epc_app = Applicability.REQUIRED
    elif residential is False or epc_exempt is True or transfer is False:
        epc_app = Applicability.NOT_REQUIRED
    requirement(
        AnalysisKind.EPC,
        "FL_EPC_REQUIRED",
        epc_app,
        (
            "Residential transfer evidence, EPC Bouw availability and "
            "statutory exceptions must be established; presence is not "
            "signature/registry authentication."
        ),
    )

    year = context.value("property.construction_year")
    accessible = context.value("property.accessible")
    area = context.value("property.aggregate_accessible_area_m2")
    larger = context.value("property.part_of_larger_construction")
    asbestos_app = Applicability.CONDITIONAL
    if isinstance(year, int) and not isinstance(year, bool):
        if year >= 2001 or accessible is False or transfer is False:
            asbestos_app = Applicability.NOT_REQUIRED
        elif year < 2001 and accessible is True and transfer is True:
            if (
                type(area) in (int, float) and isinstance(area, (int, float)) and area >= 20
            ) or larger is True:
                asbestos_app = Applicability.REQUIRED
            elif (
                type(area) in (int, float)
                and isinstance(area, (int, float))
                and area < 20
                and larger is False
            ):
                asbestos_app = Applicability.NOT_REQUIRED
    requirement(
        AnalysisKind.ASBESTOS_CERTIFICATE,
        "FL_ASBESTOS_REQUIRED",
        asbestos_app,
        (
            "Confirm reference construction year, accessibility, aggregated "
            "area/larger-construction exception and qualifying transfer."
        ),
        AsbestosVariant.PRIVATE_UNIT,
    )
    for code, variant, condition in [
        (
            "FL_ASBESTOS_COMMON_PARTS",
            AsbestosVariant.COMMON_PARTS,
            context.value("property.forced_coownership"),
        ),
        (
            "FL_ASBESTOS_COMMONLY_USED",
            AsbestosVariant.COMMONLY_USED_PARTS,
            context.value("property.commonly_used_parts"),
        ),
    ]:
        app = asbestos_app if condition is True else Applicability.CONDITIONAL
        if code == "FL_ASBESTOS_COMMON_PARTS" and condition is True:
            # The VME possession duty from 2027 does not depend on a sale.
            app = Applicability.CONDITIONAL
            if isinstance(year, int) and not isinstance(year, bool):
                if year >= 2001 or accessible is False:
                    app = Applicability.NOT_REQUIRED
                elif accessible is True and (
                    (type(area) in (int, float) and isinstance(area, (int, float)) and area >= 20)
                    or larger is True
                ):
                    app = Applicability.REQUIRED
        if condition is False:
            app = Applicability.NOT_REQUIRED
        requirement(
            AnalysisKind.ASBESTOS_CERTIFICATE,
            code,
            app,
            (
                "Ownership configuration and pre-2001 accessible-construction "
                "conditions require evidence; an existing common-parts "
                "certificate may already need disclosure."
            ),
            variant,
        )

    electrical_app = Applicability.CONDITIONAL
    old = context.value("electrical.installation_before_1981")
    complete = context.value("electrical.complete_conformity_inspection")
    exempt = context.value("transaction.electrical_sale_exemption")
    if residential is False or transfer is False or exempt is True:
        electrical_app = Applicability.NOT_REQUIRED
    elif (
        residential is True
        and transfer is True
        and exempt is False
        and old is True
        and complete is False
    ):
        electrical_app = Applicability.REQUIRED
    requirement(
        AnalysisKind.ELECTRICAL_INSPECTION,
        "BE_ELECTRICAL_REQUIRED",
        electrical_app,
        (
            "Installation history, complete prior inspection, 25-year report "
            "period, significant modifications and documented "
            "demolition/renewal exception need review; a new report is not "
            "universally required."
        ),
    )
    ground_transfer = context.value("transaction.ground_transfer")
    soil_app = Applicability.REQUIRED if ground_transfer is True else Applicability.CONDITIONAL
    if ground_transfer is False:
        soil_app = Applicability.NOT_REQUIRED
    requirement(
        AnalysisKind.SOIL_CERTIFICATE,
        "FL_SOIL_REQUIRED",
        soil_app,
        (
            "An applicable bodemattest is needed before a qualifying ground "
            "transfer agreement, including non-risk ground; inheritance and "
            "statutory transfer definitions must be checked."
        ),
    )

    epcs = [d for d in active if d.kind == AnalysisKind.EPC]
    labels = {str(f.value) for d in epcs if (f := d.one("label"))}
    if labels & {"E", "F"}:
        details = "Residential use at the qualifying transfer and exceptions must be verified."
        severity = Severity.REVIEW
        if residential is True:
            details = (
                "For a qualifying transfer, the current baseline targets EPC D or "
                "better within six years."
            )
            if transfer is True:
                severity = Severity.WARNING
            deed = context.value("transaction.authentic_deed_date", allow_unverified=True)
            if (
                deed
                and date.fromisoformat(str(deed)) <= when
                and transfer is True
                and context.value("transaction.renovation_exemption") is False
                and context.value("transaction.existing_renovation_obligation") is False
            ):
                details += (
                    (
                        " Provisional deadline using an unverified buyer-provided deed date "
                        "(confirm with your notary): "
                        if context.facts["transaction.authentic_deed_date"].authority
                        == Authority.UNVERIFIED
                        else " Indicative deadline: "
                    )
                    + add_months(date.fromisoformat(str(deed)), 72).isoformat()
                    + "."
                )
            else:
                details += (
                    " Absolute deadline unavailable: relevant "
                    "deed/right-establishment date, exceptions or an inherited "
                    "remaining period are not established."
                )
        if len(labels) > 1:
            severity = Severity.REVIEW
            details = "Conflicting EPC labels require review before applying an obligation."
        if context.value("transaction.renovation_exemption") is True:
            severity = Severity.REVIEW
            details = (
                "An explicit exemption is recorded; verify its scope before "
                "applying the residential renovation rule."
            )
        if any(
            (e := d.one("valid_until")) and date.fromisoformat(str(e.value)) < when for d in epcs
        ):
            severity = Severity.REVIEW
            details = (
                "An expired EPC cannot establish the current label; "
                "obtain current applicable evidence."
            )
        emit(
            "FL_EPC_RENOVATION",
            severity,
            "EPC E/F: renovation applicability requires attention",
            details,
            epcs,
        )
    for doc in active:
        if doc.kind == AnalysisKind.ASBESTOS_CERTIFICATE:
            end = doc.one("valid_until")
            if end and date.fromisoformat(str(end.value)) < when:
                emit(
                    "FL_ASBESTOS_VALIDITY",
                    Severity.WARNING,
                    "Printed asbestos certificate validity has expired",
                    (
                        "The explicitly printed validity date precedes the evaluation "
                        "date. Without a date, validity remains unverified; no universal "
                        "ten-year period is inferred."
                    ),
                    [doc],
                )
        elif doc.kind == AnalysisKind.ELECTRICAL_INSPECTION:
            conforming = doc.one("conforming")
            if conforming and conforming.value is False:
                inspection = doc.one("inspection_type")
                sale = inspection is not None and str(inspection.value).casefold() in {
                    "verkoop",
                    "controle bij verkoop",
                    "verkoopkeuring",
                }
                details = (
                    "Inspection context is not established as a sale inspection; the "
                    "18-month sale period cannot be applied."
                )
                if sale:
                    details = (
                        "For the relevant negative sale inspection, the buyer generally "
                        "remedies the installation and obtains a new inspection within 18 "
                        "months of the authentic deed."
                    )
                    deed = context.value("transaction.authentic_deed_date")
                    details += (
                        (
                            " Indicative deadline: "
                            + add_months(date.fromisoformat(str(deed)), 18).isoformat()
                            + "."
                        )
                        if deed
                        else " Absolute deadline unavailable: authentic-deed date is missing."
                    )
                emit(
                    "BE_ELECTRICAL_NEGATIVE_SALE",
                    Severity.WARNING if sale else Severity.REVIEW,
                    "Electrical inspection is non-conforming",
                    details,
                    [doc],
                )
        elif doc.kind == AnalysisKind.SOIL_CERTIFICATE:
            risk = doc.one("risk_ground")
            if risk and risk.value is True:
                emit(
                    "FL_SOIL_RISK_GROUND",
                    Severity.REVIEW,
                    "Risk-ground statement requires transfer review",
                    (
                        "Verify additional transfer requirements, including an applicable "
                        "orienting soil investigation or exemption. This finding does not "
                        "conclude that sale is prohibited."
                    ),
                    [doc],
                )
    soil_req = next(r for r in requirements if r.kind == AnalysisKind.SOIL_CERTIFICATE)
    if soil_req.missing_parcels:
        emit(
            "FL_SOIL_PARCEL_COVERAGE",
            Severity.BLOCKING_DATA_GAP,
            "Soil certificate parcel coverage is incomplete",
            "The dossier does not demonstrate bodemattest coverage for every official parcel.",
            [d for d in active if d.kind == AnalysisKind.SOIL_CERTIFICATE],
        )
    for doc in context.documents:
        if doc.association != AssociationStatus.MATCHED:
            emit(
                "DOCUMENT_PROPERTY_ASSOCIATION",
                Severity.WARNING
                if doc.association == AssociationStatus.MISMATCH
                else Severity.REVIEW,
                "Document/property association requires review",
                "Document "
                + str(doc.id)
                + ": "
                + doc.association.value
                + ". Its document-level facts are excluded from substantive property rules.",
                [doc],
            )
    return RuleResult(tuple(requirements), tuple(findings))
