"""Small synthetic PDFs generated locally; no customer or copied official content."""

from io import BytesIO

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from viesett.domain.intelligence import AnalysisKind

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
SAMPLES = {
    AnalysisKind.EPC: EPC,
    AnalysisKind.ASBESTOS_CERTIFICATE: ASBESTOS,
    AnalysisKind.ELECTRICAL_INSPECTION: ELECTRICAL,
    AnalysisKind.SOIL_CERTIFICATE: SOIL,
}


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
