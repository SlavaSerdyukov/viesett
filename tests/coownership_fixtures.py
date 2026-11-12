from viesett.domain.intelligence import AnalysisKind

IDENTITY_NL = (
    "VME: Residentie Fictief\nVME ondernemingsnummer: 0000000"
    "196\nGebouwadres: Teststraat 42, 9000 Gent\nKavel: A1\nCon"
    "text: gebouw\nToestand op: 2026-11-12\n"
)
IDENTITY_FR = (
    "ACP: Résidence Fictive\nNuméro d'entreprise ACP: 0000000"
    "196\nAdresse de l'immeuble: Teststraat 42, 9000 Gent\nLot"
    ": A1\nContexte: immeuble\nSituation au: 2026-11-12\n"
)
SYNDIC_NL = (
    "Inlichtingen artikel 3.94\n"
    + IDENTITY_NL
    + "Werkkapitaal: EUR 12000,00\nReservekapitaal: EUR 50000,0"
    "0\nAchterstallen verkoper: EUR 0,00\n"
    "Reserveoproepen: geen\nHangende rechtszaken: geen\n"
    "Volledige dekking gewone en buitengewone AV: 2023-11-12 tot 2026-11-12\n"
    "Volledige dekking afrekeningen: 2024-11-12 tot 2026-11-12\n"
    "Laatste goedgekeurde balans: SYN-BAL-2025\nGoedgekeurd op AV: 2026-03-01\n"
    "Aanvraagdatum: 2026-11-01\nAntwoorddatum: 2026-11-12\n"
)
SYNDIC_FR = (
    "Renseignements article 3.94\n"
    + IDENTITY_FR
    + "Fonds de roulement: EUR 12000,00\nFonds de réserve: EUR "
    "50000,00\nArriérés du vendeur: EUR 0,00\n"
    "Appels de fonds réserve: aucun\nProcédures judiciaires en cours: aucune\n"
    "Couverture complète AG ordinaires et extraordinaires: 2023-11-12 au 2026-11-12\n"
    "Couverture complète décomptes: 2024-11-12 au 2026-11-12\n"
    "Dernier bilan approuvé: SYN-BAL-2025\nApprouvé par AG le: 2026-03-01\n"
    "Date de demande: 2026-11-01\nDate de réponse: 2026-11-12\n"
)
DEED_NL = (
    "Basisakte\n" + IDENTITY_NL + "Private eenheid: Appartement A1\nAandeel gemeenschappeli"
    "jke delen: 75/1000\nBijbehorende kavel: Kelder K1\n"
)
DEED_FR = (
    "Acte de base\n" + IDENTITY_FR + "Désignation privative: Appartement A1\nQuote-part des pa"
    "rties communes: 75/1000\nLot annexe lié: Cave K1\n"
)
AGM_NL = (
    "Notulen gewone algemene vergadering\n"
    + IDENTITY_NL
    + "Vergaderdatum: 2026-03-01\nAgendapunt 1: dakrenovatie\nProjectreferentie: ROOF-2026\n"
    "Besluit: goedgekeurd\nGoedgekeurd budget: EUR 120000,00\n"
    "Reserveallocatie project: EUR 40000,00\n"
    "Financieringsbron: reservekapitaal\nAlgemene kostensleut"
    "el van toepassing: ja\nStemresultaat: 4/5\n"
    "Geplande uitvoering: 2027-01-10\n"
)
AGM_FR = (
    "Procès-verbal assemblée générale ordinaire\n"
    + IDENTITY_FR
    + "Date de l'assemblée: 2026-03-01\nPoint 1: rénovation toi"
    "ture\nRéférence du projet: ROOF-2026\n"
    "Décision: approuvé\nBudget approuvé: EUR 120000,00\nAffec"
    "tation réserve au projet: EUR 40000,00\n"
    "Source de financement: fonds de réserve\nQuote-part géné"
    "rale applicable: oui\nRésultat du vote: 4/5\n"
    "Exécution prévue: 2027-01-10\n"
)
CALL_NL = (
    "Kapitaaloproep\n" + IDENTITY_NL + "Oproepreferentie: CALL-2026\nProjectreferentie: ROOF-2026\n"
    "Oproep totaal: EUR 120000,00\nOproep voor deze kavel: EUR 9000,00\nVervaldatum: 2026-12-01\n"
    "Fondstype: buitengewoon\nOproep dekt volledig project: ja\n"
)
CHARGES_NL = (
    "Periodieke afrekening\n" + IDENTITY_NL + "Periode: 2026-01-01 tot 2026-06-30\n"
    "Gewone gemeenschappelijke lasten: EUR 2400,00\nBuitengewone lasten: EUR 500,00\n"
    "Reservebijdrage: EUR 150,00\nBijdrage werkkapitaal: EUR 200,00\nTe betalen: EUR 100,00\n"
)
BALANCE_NL = (
    "Balans\n" + IDENTITY_NL + "Balansdatum: 2025-12-31\nGoedgekeurd op AV: 2026-03-01\n"
    "Bank en kas totaal: EUR 62000,00\nWerkkapitaal: EUR 12000,00\nReservekapitaal: EUR 50000,00\n"
    "Balansreferentie: SYN-BAL-2025\n"
    "Vorderingen totaal: EUR 4000,00\nSchulden totaal: EUR 2000,00\n"
)

SAMPLES = {
    AnalysisKind.SYNDIC_INFORMATION: (SYNDIC_NL, SYNDIC_FR),
    AnalysisKind.AGM_MINUTES: (AGM_NL, AGM_FR),
    AnalysisKind.EXTRAORDINARY_AGM_MINUTES: (
        AGM_NL.replace("Notulen gewone", "Notulen buitengewone"),
        AGM_FR.replace("ordinaire\n", "extraordinaire\n"),
    ),
    AnalysisKind.BASIS_DEED: (DEED_NL, DEED_FR),
    AnalysisKind.CO_OWNERSHIP_REGULATIONS: (
        "Reglement van mede-eigendom\n" + IDENTITY_NL + "Beroepsgebruik: toestemming vereist\n",
        "Règlement de copropriété\n" + IDENTITY_FR + "Usage professionnel: autorisation requise\n",
    ),
    AnalysisKind.INTERNAL_RULES: (
        "Reglement van interne orde\n" + IDENTITY_NL + "Huisdieren: toestemming vereist\n",
        "Règlement d'ordre intérieur\n" + IDENTITY_FR + "Animaux: autorisation requise\n",
    ),
    AnalysisKind.PERIODIC_CHARGE_STATEMENT: (
        CHARGES_NL,
        "Décompte périodique des charges\n"
        + IDENTITY_FR
        + "Période: 2026-01-01 au 2026-06-30\nCharges communes ordinaires: EUR 2400,00\n",
    ),
    AnalysisKind.BALANCE_SHEET: (
        BALANCE_NL,
        "Bilan de copropriété\n"
        + IDENTITY_FR
        + "Date du bilan: 2025-12-31\nApprouvé par AG le: 2026-03-0"
        "1\nFonds de réserve: EUR 50000,00\n",
    ),
    AnalysisKind.CAPITAL_CALL: (
        CALL_NL,
        "Appel de fonds\n"
        + IDENTITY_FR
        + "Référence de l'appel: CALL-2026\nTotal de l'appel: EUR 120000,00\n",
    ),
    AnalysisKind.RESERVE_FUND_STATEMENT: (
        "Reservekapitaalstaat\n" + IDENTITY_NL + "Reservekapitaal: EUR 50000,00\n",
        "État du fonds de réserve\n" + IDENTITY_FR + "Fonds de réserve: EUR 50000,00\n",
    ),
    AnalysisKind.OTHER_CO_OWNERSHIP_DOCUMENT: (
        "Mede-eigendomsdocument\n" + IDENTITY_NL,
        "Document de copropriété\n" + IDENTITY_FR,
    ),
}
