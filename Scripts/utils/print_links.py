from typing import Dict, Iterable, Tuple
from shapely.geometry import Point, LineString
import numpy as np

class GeometryType:
    name: str
    geom_type: str

    def __new__(cls, obj):
        pass


class Node(GeometryType):
    name = "NODE"
    geom_type = "Point"
    special_attr_names = []

    def __new__(cls, node):
        return Point(node.x, node.y)


class Link(GeometryType):
    name = "LINK"
    geom_type = "LineString"
    special_attr_names = ["i_node", "j_node", "modes"]

    def __new__(cls, link):
        return LineString(link.shape)

class Line(GeometryType):
    name = "TRANSIT_LINE"
    geom_type = "Point"
    special_attr_names = ["mode", "vehicle"]

    def __new__(cls, line):
        return Node(next(line.segments()).i_node)


class Segment(GeometryType):
    name = "TRANSIT_SEGMENT"
    geom_type = "Point"
    special_attr_names = ["line", "link"]

    def __new__(cls, segment):
        return Node(segment.i_node)

def attr_value(attr_name, obj, geom_type):
    value = getattr(obj, attr_name)
    if attr_name in geom_type.special_attr_names:
        try:
            return "".join(map(str, value)) if isinstance(value, frozenset) else str(value)
        except AttributeError:
            return "None"
    if isinstance(value, np.generic):
        return value.item()
    return value


def geometries(attrs: Dict[str, str],
               objects: Iterable,
               geom_type: GeometryType) -> Tuple[Iterable, dict]:
    """Turn EMME network objects into GeoJSON records.

    Parameters
    ----------
    attrs : Dict[str, str]
        Dictionary mapping attribute names to their types
    objects : Iterable
        Iterator over network objects (links or nodes or segments)
    geom_type : GeometryType
        Node or Link or Segment geometry type

    Returns
    -------
    Iterable
        Iterator of GeoJSON records
    dict
        Fiona schema of record types
    """

    recs = ({
        "geometry": geom_type(obj),
        "properties": {
            "id": obj.id,
            **{attr_name.lstrip("@#"): attr_value(attr_name, obj, geom_type) for attr_name in attrs.keys()},
        }
    } for obj in objects)
    
    schema_properties = {"id": "str"}
    for attr_name, attr_type in attrs.items():
            schema_properties[attr_name.lstrip("@#")] = attr_type
    schema = {
        "geometry": geom_type.geom_type,
        "properties": schema_properties,
    }

    return recs, schema


def print_links(network, resultdata):
    """Dump link attributes with wkt coordinates to file.

    Parameters
    ----------
    network : inro.emme.network.Network
        Network where whole-day results are stored
    """
    attr_names = network.attributes("LINK")
    resultdata.print_line(
        "Link\tnode_i\tnode_j" + "\t".join(attr_names), "links")
    for link in network.links():
        wkt = LineString(link.shape).wkt
        attrs = "\t".join([str(link[attr]) for attr in attr_names])
        resultdata.print_line(
            wkt + "\t" + str(link.i_node.id) + "\t" + str(link.j_node.id) + "\t" + attrs, "links")
    resultdata.flush()
