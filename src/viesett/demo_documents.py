"""Small synthetic PDFs generated locally; no customer or copied official content."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

ADDRESS = "Adres: Teststraat 42, 9000 Gent"
EPC = (
    "Energieprestatiecertificaat\nVEKA\nEPC Residentieel\n" + ADDRESS + "\n"
    "Certificaatnummer: SYNTHETIC-EPC-2026\nDatum van opmaak: 12/01/2026\n"
    "Geldig tot: 12/01/2036\nEPC-label: E\nEnergiescore: 450 kWh/m²jaar\n"
)
ASBESTOS = (
    "Asbestattest\nOVAM\n" + ADDRESS + "\nAttestnummer: SYNTHETIC-ASB-2026\n"
    "Afgeleverd op: 10/01/2026\nGeldig tot: 10/01/2031\nEindconclusie: niet-asbestveilig\n"
    "Aantal asbestmaterialen: 3\nOnderwerp: privatieve delen\nBeheren: dakmateriaal\n"
)
ELECTRICAL = (
    "Verslag controle elektrische installatie\nAREI\n" + ADDRESS + "\n"
    "Controleorganisme: Synthetic inspection body\nVerslagnummer: SYNTHETIC-ELEC-2026\n"
    "Keuringsdatum: 11/01/2026\nType controle: verkoop\nBesluit: niet-conform\n"
    "Inbreuk 1: ontbrekende beschermingsgeleider\nOpvolging: hercontrole vereist\n"
)
SOIL = (
    "Bodemattest\nOVAM\nKadastrale gegevens\nReferentie: SYNTHETIC-SOIL-2026\n"
    "Datum: 10/01/2026\nAfdeling: 11001\nSectie: B\nPerceelnummer: 0001/00S000\n"
    "CaPaKey: 11001B0001/00S000\nCaPaKey: 11001B0009/00G004\n"
    "Deze grond is niet opgenomen in het Grondeninformatieregister.\n"
    "OVAM heeft geen aanwijzingen dat deze grond een risicogrond is.\n"
)


def text_pdf(*pages: str, compress: bool = False, encrypted: bool = False) -> bytes:
    writer = PdfWriter()
    for text in pages:
        page = writer.add_blank_page(width=595, height=842)
        font = DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
        )
        commands = [b"q 1 1 1 rg 0 0 595 842 re f Q", b"BT /F1 11 Tf 40 790 Td 16 TL"]
        for line in text.splitlines():
            escaped = (
                line.encode("cp1252")
                .replace(b"\\", b"\\\\")
                .replace(b"(", b"\\(")
                .replace(b")", b"\\)")
            )
            commands.append(b"(" + escaped + b") Tj T*")
        commands.append(b"ET")
        stream = DecodedStreamObject()
        stream.set_data(b"\n".join(commands))
        page[NameObject("/Contents")] = writer._add_object(stream)
        if compress:
            page.compress_content_streams()
    if encrypted:
        writer.encrypt("synthetic-test-password")
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


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
