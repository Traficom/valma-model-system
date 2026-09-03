from typing import Iterable, Tuple
from shapely.geometry import Point, LineString
import numpy as np
from itertools import tee

class GeometryType:
    name: str
    geom_type: str
    attrs = ["data1", "data2", "data3"]

    def __new__(cls, obj):
        pass


class Node(GeometryType):
    name = "NODE"
    geom_type = "Point"

    def __new__(cls, node):
        return Point(node.x, node.y)


class Link(GeometryType):
    name = "LINK"
    geom_type = "LineString"
    attrs = GeometryType.attrs + ["type",  "num_lanes", "volume_delay_func"]

    def __new__(cls, link):
        return LineString(link.shape)

class Line(GeometryType):
    name = "TRANSIT_LINE"
    geom_type = "Point"

    def __new__(cls, line):
        return Node(next(line.segments()).i_node)


class Segment(GeometryType):
    name = "TRANSIT_SEGMENT"
    geom_type = "Point"

    def __new__(cls, segment):
        return Node(segment.i_node)

def attr_type(attr_name, obj):
    value = attr_value(attr_name, obj)
    if isinstance(value, (bool, np.bool_)):
        return "bool"
    if isinstance(value, (int, np.integer)):
        return "int"
    if isinstance(value, (float, np.floating)):
        return "float"
    if isinstance(value, str):
        return "str"
    raise TypeError(f"Unsupported attribute type: {type(value)}")

def attr_value(attr_name, obj):
    if attr_name == "modes":
        return "".join([mode.id for mode in obj.modes])
    if attr_name == "line_id":
        return str(obj.line.id)
    if attr_name == "link_id":
        return str(obj.link.id)
    if attr_name in ["mode", "vehicle", "i_node", "j_node", "modes"]:
        return str(getattr(obj, attr_name).id)
    else:
        return obj[attr_name]


def geometries(attr_names: Iterable[str],
               objects: Iterable,
               geom_type: GeometryType) -> Tuple[Iterable, dict]:
    """Turn EMME network objects into GeoJSON records.

    Parameters
    ----------
    attr_names : List of str
        List of extra attributes in network objects
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
    objects, objects_for_schema = tee(objects)
    first_obj = next(iter(objects_for_schema), None)

    recs = ({
        "geometry": geom_type(obj),
        "properties": {
            "id": obj.id,
            **{attr_name.lstrip("@#"): attr_value(attr_name, obj) for attr_name in attr_names},
        }
    } for obj in objects)
    
    schema_properties = {"id": "str"}
    for attr_name in attr_names:
            schema_properties[attr_name.lstrip("@#")] = attr_type(attr_name, first_obj)
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
