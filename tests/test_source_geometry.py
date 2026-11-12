import pytest

from tests.official_fixtures import POINT, POLYGON
from viesett.domain.property import Geometry
from viesett.integrations.geometry import parse_gml, to_wgs84
from viesett.integrations.http import SourceError


def test_native_crs_is_preserved_and_transform_is_explicit_and_repeatable() -> None:
    native = parse_gml({"gml": POLYGON})
    assert native and native.crs == "EPSG:31370"
    projected = to_wgs84(native)
    assert projected.crs == "EPSG:4326" and projected.type == "Polygon"
    assert native.crs == "EPSG:31370" and projected == to_wgs84(native)
    point = parse_gml({"gml": POINT})
    assert point and to_wgs84(point).type == "Point"
    assert to_wgs84(projected) == projected
    assert parse_gml(None) is None


@pytest.mark.parametrize(
    "gml",
    [
        "<!DOCTYPE gml:Point [<!ENTITY private SYSTEM 'file:///etc/passwd'>]><gml:Point>&private;</gml:Point>",
        "<gml:Point>",
        POINT.replace("31370", "99999"),
        POINT.replace("140252.76", "NaN"),
        POLYGON.replace("140250 198790</gml:posList>", "140251 198791</gml:posList>"),
        POLYGON.replace("198790 140260", "198790 7 140260", 1),
    ],
)
def test_bad_and_unsafe_gml_is_invalid(gml: str) -> None:
    with pytest.raises(SourceError):
        parse_gml({"gml": gml})


def test_lambert_2008_and_multipolygon_are_supported() -> None:
    lambert = Geometry(type="Point", crs="EPSG:3812", coordinates=(640250, 698790))
    assert to_wgs84(lambert).crs == "EPSG:4326"
    multi = POLYGON.replace("<gml:Polygon ", "<gml:MultiSurface ").replace(
        "</gml:Polygon>", "</gml:MultiSurface>"
    )
    # A MultiSurface contains Polygon members; no arbitrary CRS is inferred.
    outer = (
        multi.split(">")[0]
        + "><gml:surfaceMember>"
        + POLYGON
        + "</gml:surfaceMember></gml:MultiSurface>"
    )
    geometry = parse_gml({"gml": outer})
    assert geometry and geometry.type == "MultiPolygon"
    assert to_wgs84(geometry).type == "MultiPolygon"
