from collections import defaultdict
from datetime import date
from decimal import Decimal
from fractions import Fraction
from uuid import UUID

from viesett.coownership.catalog import CATALOG
from viesett.coownership.context import (
    CrossDocumentContext,
    Fact,
    fact_date,
    ids,
    initial_association,
    money,
    private_lot_corroborated,
)
from viesett.coownership.coverage import coverage, years_before
from viesett.coownership.financial import exposure
from viesett.coownership.projects import projects
from viesett.domain.coownership import (
    CO_KINDS,
    AssociationResult,
    BuyerQuestion,
    CapitalCall,
    CoFinding,
    CoOwnershipIdentity,
    CoSnapshot,
    CoverageInterval,
    DecisionStatus,
    Litigation,
    MoneyObservation,
    PackageComponent,
    PackageStatus,
    Share,
)
from viesett.domain.intelligence import AnalysisKind, AssociationStatus
from viesett.domain.types import Severity


def share(fact: Fact, lot: str | None) -> Share:
    numerator, denominator = str(fact.field.value).split("/")
    return Share(
        numerator=int(numerator),
        denominator=int(denominator),
        original_representation=str(fact.field.value),
        basis="GENERAL_OWNERSHIP_SHARE"
        if fact.key == "share"
        else "EXPLICIT_EXPENSE_ALLOCATION_KEY",
        context=fact.field.group,
        lot=lot,
        effective_date=fact.field.effective_date,
        evidence_ids=[fact.evidence_id],
    )


def evaluate(context: CrossDocumentContext, input_hash: str = "") -> CoSnapshot:
    findings: dict[str, CoFinding] = {}
    questions: dict[str, BuyerQuestion] = {}

    def emit(
        code: str,
        key: str,
        severity: Severity,
        summary: str,
        reason: str,
        evidence: list[UUID],
        role: str = "SYNDIC",
    ) -> None:
        metadata = CATALOG[code]
        if (metadata.effective_from and context.evaluation_date < metadata.effective_from) or (
            metadata.effective_to and context.evaluation_date > metadata.effective_to
        ):
            return
        identity = code + ":" + key
        findings[identity] = CoFinding(
            key=identity,
            code=code,
            severity=severity,
            summary=summary,
            reason=reason,
            evidence_ids=sorted(set(evidence)),
            check=CATALOG[code],
        )
        text = {
            "NOTARY": (
                "Confirm the applicable expense key and which party "
                "bears this cost under the transfer agreement and "
                "Article 3.94 timing rules."
            ),
            "SYNDIC": (
                "Please clarify this documented inconsistency or "
                "provide the missing co-ownership information: "
            )
            + summary,
            "SELLER": "Please provide the missing property-specific co-ownership information: "
            + summary,
        }[role]
        if role == "NOTARY" and code == "UNIT_CONSISTENCY":
            text = "Confirm which private lot and attached lots belong to the purchased unit."
        elif role == "NOTARY" and code == "CO_GOVERNANCE_RESTRICTION":
            text = "Clarify the documented restriction, its scope and effect for the purchased lot."
        questions[identity] = BuyerQuestion.model_validate(
            {
                "key": identity,
                "code": code,
                "target_role": role,
                "question_text": text,
                "reason": reason,
                "evidence_ids": sorted(set(evidence)),
            }
        )

    co_docs = [d for d in context.documents if d.kind in CO_KINDS]
    associations = [
        AssociationResult(
            document_id=d.id,
            status=initial_association(d, context.property),
            reason="Explicit building components compared with the current official identity",
            scope="PRIVATE_UNIT" if d.value("lot") or d.value("box_number") else "BUILDING",
        )
        for d in co_docs
    ]
    matched = [
        d
        for d, a in zip(co_docs, associations, strict=True)
        if a.status == AssociationStatus.MATCHED
    ]
    future_documents = set()
    for doc, association in zip(co_docs, associations, strict=True):
        dates = [
            value
            for name in ("as_of", "response_date", "meeting_date", "balance_date")
            if (value := fact_date(doc.one(name))) is not None
        ]
        if dates and max(dates) > context.evaluation_date:
            future_documents.add(doc.id)
            if doc in matched:
                matched.remove(doc)
            association.status = AssociationStatus.UNVERIFIED
            association.reason = "Document effective date is after the evaluation date"
    enterprises = {
        str(d.value("enterprise_number")) for d in matched if d.value("enterprise_number")
    }
    # A single matched-building anchor can strengthen an otherwise addressless
    # organizational document, never override an explicit different address.
    if len(enterprises) == 1:
        for doc, association in zip(co_docs, associations, strict=True):
            if (
                association.status == AssociationStatus.UNVERIFIED
                and doc.id not in future_documents
                and not doc.value("address")
                and str(doc.value("enterprise_number")) in enterprises
            ):
                association.status = AssociationStatus.MATCHED
                association.reason = (
                    "Exact enterprise number corroborated by one matched-building identity"
                )
                matched.append(doc)
    for doc, association in zip(co_docs, associations, strict=True):
        if association.status in {AssociationStatus.MISMATCH, AssociationStatus.POSSIBLE_MATCH}:
            emit(
                "ADDRESS_CONSISTENCY"
                if association.status == AssociationStatus.MISMATCH
                else "UNIT_CONSISTENCY",
                str(doc.id),
                Severity.WARNING
                if association.status == AssociationStatus.MISMATCH
                else Severity.REVIEW,
                "Document property/unit association needs review",
                "Excluded from substantive co-ownership state.",
                ids(doc.fields),
            )
    if len(enterprises) > 1:
        emit(
            "CO_OWNERSHIP_IDENTITY_CONSISTENCY",
            "enterprise",
            Severity.WARNING,
            "Different VME/ACP enterprise numbers for the selected building",
            "Resolve the association identity before combining funds, works or exposure.",
            ids([f for d in matched for f in d.all("enterprise_number")]),
        )
    # Other supported documents can supply consistency signals, never new listing parsing.
    for doc in context.documents:
        for fact in doc.fields:
            if fact.field.key.endswith(".parcel.capakey") and context.property.parcels:
                if fact.field.value not in {p.capakey for p in context.property.parcels}:
                    emit(
                        "PARCEL_CONSISTENCY",
                        str(doc.id),
                        Severity.WARNING,
                        "Document parcel differs from official property",
                        "Verify which parcel the document covers; no property facts are promoted.",
                        [fact.evidence_id],
                    )
        if doc.kind not in CO_KINDS:
            from viesett.document_intelligence.association import associate

            standard_status = associate([f.field for f in doc.fields], context.property).status
            if standard_status == AssociationStatus.MISMATCH:
                emit(
                    "ADDRESS_CONSISTENCY",
                    str(doc.id),
                    Severity.WARNING,
                    "Document address/unit differs from official property",
                    "Compare explicit property components before using this document.",
                    ids(doc.fields),
                )

    def unique(key: str) -> str | None:
        values = {str(d.value(key)) for d in matched if d.value(key) is not None}
        return next(iter(values)) if len(values) == 1 else None

    purchased_lots = {
        str(d.value("lot"))
        for d in matched
        if d.kind == AnalysisKind.BASIS_DEED
        and d.value("lot")
        and private_lot_corroborated(d, context.property)
    }
    lot = next(iter(purchased_lots)) if len(purchased_lots) == 1 else None
    for doc in matched:
        if lot and doc.value("lot") and str(doc.value("lot")) != lot:
            emit(
                "UNIT_CONSISTENCY",
                str(doc.id),
                Severity.WARNING,
                "Document lot differs from the documented purchased lot",
                "Lot-specific arrears, calls and allocation are excluded for this document.",
                ids(doc.all("lot")),
            )
    if len(purchased_lots) > 1:
        emit(
            "UNIT_CONSISTENCY",
            "deeds",
            Severity.WARNING,
            "Purchased lot identity is inconsistent",
            "No private-lot allocation is selected arbitrarily.",
            ids([f for d in matched for f in d.all("lot")]),
        )
    shares = [
        share(f, str(d.value("lot")) if d.value("lot") else None)
        for d in matched
        for f in d.all("share")
        if d.kind == AnalysisKind.BASIS_DEED
    ]
    general = None
    if lot:
        relevant = [s for s in shares if s.lot == lot]
        if relevant:
            dated = [
                s
                for s in relevant
                if s.effective_date and s.effective_date <= context.evaluation_date
            ]
            current = (
                [
                    s
                    for s in dated
                    if s.effective_date == max(s.effective_date or date.min for s in dated)
                ]
                if dated
                else relevant
            )
            values = {Fraction(s.numerator, s.denominator) for s in current}
            if len(values) == 1:
                general = current[0].model_copy(
                    update={"evidence_ids": sorted({e for s in current for e in s.evidence_ids})}
                )
            elif len(values) > 1:
                emit(
                    "OWNERSHIP_SHARE_CONSISTENCY",
                    lot,
                    Severity.WARNING,
                    "Ownership shares conflict for the same lot/context",
                    "No share is selected for exposure until the documents are reconciled.",
                    [e for s in current for e in s.evidence_ids],
                    "NOTARY",
                )
    identity = (
        CoOwnershipIdentity(
            association_name=unique("association_name"),
            enterprise_number=next(iter(enterprises)) if len(enterprises) == 1 else None,
            building_address=unique("address"),
            syndic_name=unique("syndic_name"),
            syndic_enterprise_number=unique("syndic_enterprise_number"),
            lot_identifier=lot,
            private_unit_designation=unique("private_designation"),
            ownership_share=general,
            attached_lots=sorted(
                {
                    str(f.field.value)
                    for d in matched
                    if str(d.value("lot")) == lot
                    for f in d.all("attached_lot")
                }
            ),
            source_document_ids=sorted(d.id for d in matched),
            evidence_ids=ids(
                [
                    f
                    for d in matched
                    for f in d.fields
                    if f.key
                    in {
                        "association_name",
                        "enterprise_number",
                        "address",
                        "lot",
                        "share",
                        "attached_lot",
                    }
                ]
            ),
        )
        if matched
        else None
    )
    observations = []
    concepts = {
        "working_capital",
        "reserve_capital",
        "seller_arrears",
        "ordinary_charges",
        "extraordinary_charges",
        "reserve_contribution",
        "working_contribution",
        "cash_bank_total",
        "receivables",
        "payables",
        "amount_due",
        "credit",
    }
    for doc in matched:
        for fact in doc.fields:
            if fact.key not in concepts or (parsed := money(fact)) is None:
                continue
            if fact.key == "seller_arrears" and (
                not doc.value("lot") or (lot and str(doc.value("lot")) != lot)
            ):
                continue
            if fact.field.effective_date and fact.field.effective_date > context.evaluation_date:
                continue
            observations.append(
                MoneyObservation(
                    concept=fact.key,
                    money=parsed,
                    effective_date=fact.field.effective_date,
                    context=fact.field.context or "UNSPECIFIED",
                    lot=str(doc.value("lot"))
                    if fact.key == "seller_arrears" or fact.field.context == "LOT"
                    else None,
                    document_id=doc.id,
                    evidence_ids=[fact.evidence_id],
                )
            )

    def current_money(concept: str) -> MoneyObservation | None:
        if len(enterprises) > 1:
            return None
        rows = [
            o
            for o in observations
            if o.concept == concept and o.effective_date and o.context == "BUILDING"
        ]
        if not rows:
            return None
        latest = max(o.effective_date or date.min for o in rows)
        newest = [o for o in rows if o.effective_date == latest]
        comparable = {(o.money.amount, o.money.currency, o.context) for o in newest}
        return newest[0] if len(comparable) == 1 else None

    for concept, code in [
        ("reserve_capital", "RESERVE_CAPITAL_AMOUNT_CONSISTENCY"),
        ("working_capital", "WORKING_CAPITAL_AMOUNT_CONSISTENCY"),
    ]:
        groups: dict[tuple[date, str, str, str | None], list[MoneyObservation]] = defaultdict(list)
        for observation in observations:
            if (
                observation.concept == concept
                and observation.effective_date
                and observation.context != "UNSPECIFIED"
            ):
                groups[
                    (
                        observation.effective_date,
                        observation.context,
                        observation.money.currency,
                        observation.lot,
                    )
                ].append(observation)
        for fund_key, fund_rows in groups.items():
            if len({r.money.amount for r in fund_rows}) > 1:
                emit(
                    code,
                    str(fund_key),
                    Severity.WARNING,
                    "Comparable " + concept.replace("_", " ") + " amounts disagree",
                    (
                        "Same documented date, currency and reporting context; "
                        "different dates alone are not contradictions."
                    ),
                    [e for r in fund_rows for e in r.evidence_ids],
                )
    meetings, works, calls = projects(matched, context.evaluation_date)
    for call in calls:
        if call.lot and lot and call.lot != lot:
            call.lot_specific_amount = None
    call_groups: dict[tuple[str, date, str, str], list[CapitalCall]] = defaultdict(list)
    for call in calls:
        if call.reference and call.effective_date and call.total:
            call_groups[
                (call.reference, call.effective_date, call.lot or "building", call.total.currency)
            ].append(call)
    for call_key, call_rows in call_groups.items():
        if len({r.total.amount for r in call_rows if r.total}) > 1:
            emit(
                "CAPITAL_CALL_CONSISTENCY",
                str(call_key),
                Severity.WARNING,
                "Comparable capital-call amounts disagree",
                "Same reference, date, currency and lot context; verify instalments and revisions.",
                [e for r in call_rows for e in r.evidence_ids],
            )
    litigation = []
    uncertain_litigation = False
    for doc in matched:
        for group in sorted({f.field.group for f in doc.fields if f.key == "litigation_category"}):
            case_status = doc.value("litigation_status", group)
            if case_status != "PENDING":
                uncertain_litigation |= case_status != "CLOSED"
                continue
            fields = [f for f in doc.fields if f.field.group == group]
            litigation.append(
                Litigation(
                    subject_category=str(doc.value("litigation_category", group)),
                    status="DISCLOSED_PENDING",
                    amount_in_dispute=money(doc.one("dispute_amount", group)),
                    effective_date=fact_date(doc.one("as_of")),
                    evidence_ids=ids(fields),
                )
            )
            emit(
                "CO_PENDING_LITIGATION",
                str(doc.id) + group,
                Severity.REVIEW,
                "Pending co-ownership litigation disclosed",
                (
                    "Verify status, amounts and implications with the "
                    "syndic/notary; outcome and personal parties are not "
                    "inferred."
                ),
                ids(fields),
            )
        for fact in doc.all("restriction"):
            emit(
                "CO_GOVERNANCE_RESTRICTION",
                str(fact.evidence_id),
                Severity.REVIEW,
                "Documented " + str(fact.field.value).lower().replace("_", " ") + " restriction",
                (
                    "Source clause requires review; internal rules are not "
                    "promoted to title rights or enforceability conclusions."
                ),
                [fact.evidence_id],
                "NOTARY",
            )

    completeness = []
    components = {
        "WORKING_CAPITAL": "working_capital",
        "RESERVE_CAPITAL": "reserve_capital",
        "SELLER_ARREARS": "seller_arrears",
        "RESERVE_CAPITAL_CALLS": "calls_none",
        "PENDING_LITIGATION": "litigation_none",
    }
    for code, key in components.items():
        facts = [f for d in matched for f in d.all(key)]
        status = PackageStatus.PRESENT if facts else PackageStatus.MISSING
        if code == "SELLER_ARREARS":
            facts = [
                f
                for d in matched
                if d.value("lot") and (not lot or str(d.value("lot")) == lot)
                for f in d.all(key)
            ]
            status = (
                PackageStatus.EXPLICIT_NONE
                if facts and all(Decimal(str(f.field.value)) == 0 for f in facts)
                else PackageStatus.PRESENT
                if facts
                else PackageStatus.MISSING
            )
        if code == "RESERVE_CAPITAL_CALLS":
            reserve_calls = [c for c in calls if c.fund_type == "RESERVE_CAPITAL"]
            status = (
                PackageStatus.PRESENT
                if reserve_calls and all(c.total is not None for c in reserve_calls)
                else PackageStatus.PARTIAL
                if reserve_calls
                else PackageStatus.EXPLICIT_NONE
                if any(f.field.value is True for f in facts)
                else PackageStatus.MISSING
            )
        if code == "PENDING_LITIGATION":
            status = (
                PackageStatus.PRESENT
                if litigation
                else PackageStatus.PARTIAL
                if uncertain_litigation
                else PackageStatus.EXPLICIT_NONE
                if any(f.field.value is True for f in facts)
                else PackageStatus.MISSING
            )
        if (
            not facts
            and status == PackageStatus.MISSING
            and any(d.parse_status in {"UNSUPPORTED_LAYOUT", "UNPARSEABLE"} for d in matched)
        ):
            status = PackageStatus.UNPARSEABLE
        completeness.append(
            PackageComponent(
                code=code,
                status=status,
                reason="Explicit documentary information; absence is never zero/none.",
                evidence_ids=sorted(
                    set(
                        ids(facts)
                        + (
                            [e for c in reserve_calls for e in c.evidence_ids]
                            if code == "RESERVE_CAPITAL_CALLS"
                            else []
                        )
                    )
                ),
            )
        )
    for code, key, years in [
        ("AGM_MINUTES_3Y", "minutes_coverage", 3),
        ("PERIODIC_CHARGES_2Y", "charges_coverage", 2),
    ]:
        periods = []
        for doc in matched:
            keys = [key] + (
                ["period"]
                if doc.kind == AnalysisKind.PERIODIC_CHARGE_STATEMENT and years == 2
                else []
            )
            for name in keys:
                start, end = fact_date(doc.one(name + "_start")), fact_date(doc.one(name + "_end"))
                if start and end and start <= end:
                    periods.append(
                        CoverageInterval(
                            start=start,
                            end=end,
                            evidence_ids=ids(doc.all(name + "_start") + doc.all(name + "_end")),
                        )
                    )
        result = coverage(context.evaluation_date, years, periods)
        status = (
            PackageStatus.PRESENT
            if not result.gaps
            else PackageStatus.PARTIAL
            if result.periods_present
            else PackageStatus.MISSING
        )
        completeness.append(
            PackageComponent(
                code=code,
                status=status,
                reason=(
                    "Rolling explicit coverage of all relevant documents; a "
                    "meeting date alone does not prove completeness."
                ),
                evidence_ids=sorted({e for p in result.periods_present for e in p.evidence_ids}),
                coverage=result,
            )
        )
    balances = [
        d
        for d in matched
        if d.value("balance_reference")
        or (
            d.kind == AnalysisKind.BALANCE_SHEET
            and d.one("approved_date")
            and (fact_date(d.one("approved_date")) or date.max) <= context.evaluation_date
        )
    ]
    latest_balance = None
    balance_present = False
    declarations = [d for d in balances if d.value("balance_reference")]
    copies = [
        d for d in balances if d.kind == AnalysisKind.BALANCE_SHEET and d.one("approved_date")
    ]
    if declarations:
        latest_date = max(fact_date(d.one("as_of")) or date.min for d in declarations)
        references = {
            str(d.value("balance_reference"))
            for d in declarations
            if (fact_date(d.one("as_of")) or date.min) == latest_date
        }
        latest_balance = next(iter(references)) if len(references) == 1 else None
        balance_present = bool(
            latest_balance and any(d.value("balance_identifier") == latest_balance for d in copies)
        )
    elif copies:
        ordered = sorted(
            copies, key=lambda d: fact_date(d.one("approved_date")) or date.min, reverse=True
        )
        latest_balance = str(ordered[0].value("balance_identifier") or ordered[0].id)
        balance_present = True
    completeness.append(
        PackageComponent(
            code="LATEST_APPROVED_BALANCE_SHEET",
            status=PackageStatus.PRESENT
            if balance_present
            else PackageStatus.PARTIAL
            if latest_balance
            else PackageStatus.MISSING,
            reason=(
                "An explicit reference alone is partial; an available balance copy with "
                "documented AGM approval is required for presence. Latestness remains documentary."
            ),
            evidence_ids=ids(
                [
                    f
                    for d in balances
                    for f in d.fields
                    if f.key in {"balance_reference", "approved_date"}
                ]
            ),
        )
    )
    if matched:
        for component in completeness:
            if component.status in {
                PackageStatus.MISSING,
                PackageStatus.PARTIAL,
                PackageStatus.UNPARSEABLE,
            }:
                emit(
                    "ARTICLE_3_94_PACKAGE_COMPLETENESS",
                    component.code,
                    Severity.BLOCKING_DATA_GAP,
                    "Missing or incomplete " + component.code.replace("_", " ").lower(),
                    (
                        "Important information check cannot be completed. "
                        "Applicability/scope must be confirmed; this does not "
                        "prohibit the transaction."
                    ),
                    component.evidence_ids,
                    "SELLER",
                )
    else:
        for component in completeness:
            component.status = PackageStatus.NOT_APPLICABLE
            component.reason = (
                "Co-ownership scope is not established for this property; not a legal exemption."
            )

    estimates = []
    for work in works:
        if work.decision_status != DecisionStatus.APPROVED:
            continue
        allocations: list[Share] = []
        general_applies = False
        for doc in matched:
            if lot and doc.value("lot") and str(doc.value("lot")) != lot:
                continue
            for reference_fact in doc.all("project_reference"):
                group = reference_fact.field.group
                if str(reference_fact.field.value) != work.reference:
                    continue
                allocations.extend(
                    share(f, str(doc.value("lot")) if doc.value("lot") else None)
                    for f in doc.all("allocation_share", group)
                    if lot and str(doc.value("lot")) == lot
                )
                general_applies |= doc.value("general_share_applies", group) is True
        dated_allocations = [s for s in allocations if s.effective_date]
        if allocations and len(dated_allocations) == len(allocations):
            latest_allocation = max(s.effective_date or date.min for s in dated_allocations)
            allocations = [s for s in dated_allocations if s.effective_date == latest_allocation]
        ratios = {Fraction(s.numerator, s.denominator) for s in allocations}
        chosen = (
            allocations[0]
            if len(ratios) == 1
            else general
            if not allocations and general_applies
            else None
        )
        conflict = (
            len(ratios) > 1
            or len(enterprises) > 1
            or bool(
                work.reference
                and sum(candidate.reference == work.reference for candidate in works) > 1
            )
        )
        for call in calls:
            if (
                call.project_reference
                and call.project_reference == work.reference
                and call.covers_full_project
                and call.total
                and work.approved_total_cost
                and call.effective_date
                and work.decision_date
                and call.effective_date >= work.decision_date
            ):
                if call.total != work.approved_total_cost:
                    conflict = True
                    emit(
                        "AGM_WORK_VS_CAPITAL_CALL",
                        work.key,
                        Severity.WARNING,
                        "Full-project call differs from approved work budget",
                        (
                            "Verify that both sources refer to the same complete "
                            "project, scope and currency."
                        ),
                        work.evidence_ids + call.evidence_ids,
                    )
        for doc in matched:
            denied = doc.one("approved_works_none")
            as_of = fact_date(doc.one("as_of")) or fact_date(doc.one("response_date"))
            if (
                denied
                and denied.field.value is True
                and as_of
                and work.decision_date
                and as_of >= work.decision_date
            ):
                conflict = True
                emit(
                    "AGM_WORK_VS_SYNDIC_INFO",
                    work.key,
                    Severity.WARNING,
                    "Syndic information denies documented approved works",
                    "Compare project scope, effective dates and subsequent decisions.",
                    work.evidence_ids + [denied.evidence_id],
                )
        estimate = exposure(work, chosen, conflict=conflict)
        estimates.append(estimate)
        emit(
            "CO_PLANNED_WORK_REVIEW",
            work.key,
            Severity.REVIEW,
            "Approved " + work.category.value.lower() + " work needs allocation/payment review",
            (
                "Budget, explicit project funding and expense key must "
                "be verified; estimated exposure never decides "
                "buyer/seller payment responsibility."
            ),
            estimate.source_evidence_ids,
            "SYNDIC" if estimate.status == "INSUFFICIENT_BUDGET" else "NOTARY",
        )

    for call in calls:
        emit(
            "CO_CAPITAL_CALL_RESPONSIBILITY",
            call.reference or str(call.evidence_ids),
            Severity.REVIEW,
            "Capital-call payment responsibility requires confirmation",
            (
                "Confirm buyer/seller allocation under the purchase "
                "agreement and Article 3.94 §2 timing; a call is not "
                "automatically buyer debt."
            ),
            call.evidence_ids,
            "NOTARY",
        )

    for doc in matched:
        accepted = fact_date(doc.one("provisional_acceptance_date"))
        contribution, previous = (
            money(doc.one("annual_reserve_contribution")),
            money(doc.one("previous_ordinary_charges")),
        )
        waiver = doc.value("reserve_waiver")
        votes = doc.value("vote_result")
        waived = waiver is True and isinstance(votes, str) and Fraction(votes) >= Fraction(4, 5)
        if (
            accepted
            and accepted <= years_before(context.evaluation_date, 5)
            and contribution
            and previous
            and contribution.currency == previous.currency
            and not waived
        ):
            if contribution.amount < previous.amount * Decimal("0.05"):
                emit(
                    "BE_RESERVE_CAPITAL_CONTRIBUTION",
                    str(doc.id),
                    Severity.REVIEW,
                    "Annual reserve contribution needs verification",
                    (
                        "Observed annual contribution is below the 5% baseline "
                        "of previous ordinary charges; verify period, scope and "
                        "any valid 4/5 waiver. Fund balance alone is not a "
                        "compliance test."
                    ),
                    ids(doc.fields),
                )
    return CoSnapshot(
        workspace_id=context.workspace_id,
        evaluation_date=context.evaluation_date,
        identity_revision=context.property.identity_revision,
        input_hash=input_hash,
        co_ownership_status="NOT_ESTABLISHED"
        if not matched
        else "REVIEW"
        if len(enterprises) > 1
        else "DOCUMENTED",
        identity=identity,
        associations=associations,
        article_3_94_completeness=completeness,
        working_capital=[o for o in observations if o.concept == "working_capital"],
        reserve_capital=[o for o in observations if o.concept == "reserve_capital"],
        current_working_capital=current_money("working_capital"),
        current_reserve_capital=current_money("reserve_capital"),
        seller_arrears=[o for o in observations if o.concept == "seller_arrears"],
        accounting_observations=[
            o
            for o in observations
            if o.concept not in {"working_capital", "reserve_capital", "seller_arrears"}
        ],
        capital_calls=calls,
        pending_litigation=litigation,
        meetings=meetings,
        planned_works=works,
        financial_exposure_estimates=estimates,
        cross_document_findings=list(findings.values()),
        questions=list(questions.values()),
        latest_balance_sheet_reference=latest_balance,
        syndic_request_date=min(
            (v for d in matched if (v := fact_date(d.one("request_date")))), default=None
        ),
        syndic_response_date=max(
            (v for d in matched if (v := fact_date(d.one("response_date")))), default=None
        ),
    )
