from typing import Iterable, Tuple
from shapely.geometry import Point, LineString

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


class Segment(GeometryType):
    name = "TRANSIT_SEGMENT"
    geom_type = "Point"

    def __new__(cls, segment):
        return Node(segment.i_node)


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
    recs = ({
        "geometry": geom_type(obj),
        "properties": {
            "id": obj.id,
            **{attr.lstrip("@#"): obj[attr] for attr in attr_names},
        }
    } for obj in objects)
    schema = {
        "geometry": geom_type.geom_type,
        "properties": {
            "id": "str",
            **{attr.lstrip("@#"): "float" for attr in attr_names}
        }
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
