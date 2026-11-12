import re
from typing import cast

from defusedxml.common import DefusedXmlException
from defusedxml.ElementTree import fromstring
from pydantic import JsonValue, ValidationError
from pyproj import Transformer, network
from pyproj.exceptions import ProjError

from viesett.domain.property import Geometry, MultiPolygonCoordinates, PolygonCoordinates, Position
from viesett.integrations.http import SourceError, object_value, string_value

GML = "{http://www.opengis.net/gml/3.2}"


def parse_gml(value: JsonValue) -> Geometry | None:
    if value is None:
        return None
    obj = object_value(value)
    gml = string_value(obj.get("gml"), maximum=250000)
    try:
        root = fromstring(gml, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        srs = root.attrib.get("srsName", "")
        match = re.fullmatch(
            r"(?:https?://www.opengis.net/def/crs/EPSG/0/|EPSG:)(31370|3812|4326)", srs
        )
        if match is None:
            raise ValueError("Unsupported source CRS")
        crs = "EPSG:" + match.group(1)
        if root.tag == GML + "Point":
            pos = root.find(GML + "pos")
            coordinates: object = (
                tuple(float(x) for x in (pos.text or "").split()) if pos is not None else ()
            )
            geometry_type = "Point"
        else:
            polygons = (
                [root] if root.tag == GML + "Polygon" else root.findall(".//" + GML + "Polygon")
            )
            if not polygons or root.tag not in {
                GML + "Polygon",
                GML + "MultiSurface",
                GML + "MultiPolygon",
            }:
                raise ValueError("Unsupported GML geometry")
            all_coordinates = []
            for polygon in polygons:
                rings = []
                for ring in polygon.findall(".//" + GML + "LinearRing"):
                    positions = ring.find(GML + "posList")
                    if positions is None or positions.attrib.get("srsDimension", "2") != "2":
                        raise ValueError("Two-dimensional positions required")
                    numbers = [float(x) for x in (positions.text or "").split()]
                    if len(numbers) % 2:
                        raise ValueError("Invalid coordinates")
                    rings.append(list(zip(numbers[::2], numbers[1::2], strict=True)))
                all_coordinates.append(rings)
            geometry_type = "Polygon" if root.tag == GML + "Polygon" else "MultiPolygon"
            coordinates = all_coordinates[0] if geometry_type == "Polygon" else all_coordinates
        return Geometry.model_validate(
            {"type": geometry_type, "crs": crs, "coordinates": coordinates}
        )
    except (DefusedXmlException, ValueError, ValidationError, SyntaxError, TypeError):
        raise SourceError("invalid_geometry", invalid=True) from None


def to_wgs84(geometry: Geometry) -> Geometry:
    if geometry.crs == "EPSG:4326":
        return geometry.model_copy(deep=True)
    # Public API; pyproj's extension re-export currently lacks an explicit type export.
    network.set_network_enabled(False)  # type: ignore[attr-defined]
    try:
        transformer = Transformer.from_crs(
            geometry.crs, "EPSG:4326", always_xy=True, allow_ballpark=False
        )

        def transform(point: Position) -> Position:
            x, y = transformer.transform(*point, errcheck=True)
            return float(x), float(y)

        if geometry.type == "Point":
            coordinates: object = transform(cast(Position, geometry.coordinates))
        elif geometry.type == "Polygon":
            coordinates = [
                [transform(p) for p in ring]
                for ring in cast(PolygonCoordinates, geometry.coordinates)
            ]
        else:
            coordinates = [
                [[transform(p) for p in ring] for ring in polygon]
                for polygon in cast(MultiPolygonCoordinates, geometry.coordinates)
            ]
        return Geometry.model_validate(
            {"type": geometry.type, "crs": "EPSG:4326", "coordinates": coordinates}
        )
    except (ProjError, ValueError):
        raise SourceError("coordinate_transformation_failed", invalid=True) from None
