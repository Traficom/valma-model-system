from typing import Dict, Callable

from parameters.assignment import volume_factors


def sum_24h(obj, networks, extras: Dict[str, Dict[str, str]],
            extra: Dict[str, str], getter: Callable):
    """
        Sums and expands attribute to 24h.

        Parameters
        ----------
        obj : Emme network object
            Node or link or segment
        networks : dict
            key : str
                Time period
            value : inro.emme.network.Network.Network
                Time-period networks
        extras : dict
            key : str
                Time period
            value : dict
                key : str
                    Assignment class
                value : str
                    Extra attribute from where time-period data is taken
        extra : dict
            key : str
                Assignment class
            value : str
                Extra attribute where to store 24h result
        getter : Callable
            get_node, get_link or get_segment
        """
    day_attr = dict.fromkeys(extra, 0.0)
    for tp in networks:
        try:
            tp_obj = getter(networks[tp], obj)
        except (AttributeError, TypeError):
            pass
        else:
            for attr in extra:
                day_attr[attr] += (tp_obj[extras[tp][attr]]
                                   / volume_factors[attr][tp])
    for attr in extra:
        obj[extra[attr]] = day_attr[attr]


def get_node(network, node):
    return network.node(node.id)


def get_link(network, link):
    return network.link(link.i_node, link.j_node)


def get_segment(network, segment):
    return network.transit_line(segment.line.id).segment(segment.number)
