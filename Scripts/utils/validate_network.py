import utils.log as log
import parameters.assignment as param


EMME_AUTO_MODE = "AUTO"
EMME_AUX_AUTO_MODE = "AUX_AUTO"
EMME_TRANSIT_MODE = "TRANSIT"
EMME_AUX_TRANSIT_MODE = "AUX_TRANSIT"

def validate(network, time_periods=param.time_periods, fares=None):
    """Validate EMME network in terms of HELMET compatibility.

    Check that:
    - all auto links have volume-delay functions defined
    - all tram links have speed defined
    - all transit lines have headways defined
    - a majority of nodes has transit fare zone defined (optional)

    Parameters
    ----------
    network : inro.emme.network.Network
        Network to be validated
    time_periods : list of str (optional)
        Time period names, default is aht, pt, iht
    fares : pandas.DataFrame
            Transit fare zone specification (optional)
    """
    transit_modes = list({m for lst in param.long_dist_transit_modes.values()
        for m in lst}) + param.local_transit_modes
    op_attr = param.line_operator_attr.replace("ut", "data")
    hdw_attrs = [f"#hdw_{tp}" for tp in time_periods]
    for line in network.transit_lines():
        if line.mode.id in transit_modes:
            for hdwy in hdw_attrs:
                if line[hdwy] < 0.02:
                    msg = "Headway missing for line {}".format(line.id)
                    log.error(msg)
                    raise ValueError(msg)
            if fares is not None and line[op_attr] not in fares:
                msg = f"No transit fares for operator id {int(line[op_attr])}"
                log.error(msg)
                raise ValueError(msg)
    validate_mode(network, param.main_mode, EMME_AUTO_MODE)
    for m in param.assignment_modes.values():
        validate_mode(network, m, EMME_AUX_AUTO_MODE)
    for m in transit_modes:
        validate_mode(network, m, EMME_TRANSIT_MODE)
    for m in param.aux_modes + [param.bike_mode]:
        validate_mode(network, m, EMME_AUX_TRANSIT_MODE)
    car_time_attrs = [f"#car_time_{tp}" for tp in time_periods]
    for link in network.links():
        if not link.modes:
            msg = "No modes defined for link {}. At minimum mode h and one more mode needs to be defined for the simulation to work".format(link.id)
            log.error(msg)
            raise ValueError(msg)
        if network.mode('h') in link.modes and len(link.modes) == 1:
            msg = "Only h mode defined for link {}. At minimum mode h and one more mode needs to be defined for the simulation to work".format(link.id)
            log.error(msg)
            raise ValueError(msg)
        if link.type == 100:
            msg = "Link id {} type must not be 100, please refer to the helmet-docs manual".format(link.id)
            log.error(msg)
            raise ValueError(msg)
        if link.type == 999:
            msg = "Link id {} type must not be 999, please refer to the helmet-docs manual".format(link.id)
            log.error(msg)
            raise ValueError(msg)
        linktype = link.type % 100
        if (linktype != 70 and link.length == 0): 
            msg = "Link {} has zero length. Link length can be zero only if linktype is 70. (vaihtokävelyt)".format(link.id)
            log.error(msg)
            raise ValueError(msg)
        if network.mode('c') in link.modes:
            if (linktype not in param.roadclasses
                    and linktype not in param.custom_roadtypes):
                msg = "Link type missing for link {}".format(link.id)
                log.error(msg)
                raise ValueError(msg)
            for attr in car_time_attrs:
                if link[attr] < 0:
                    msg = f"Negative {attr} on car link {link.id}"
                    log.error(msg)
                    raise ValueError(msg)


def validate_mode(network, m, mode_type):
    mode = network.mode(m)
    if mode is None or mode.type != mode_type:
        msg = f"{m} is not {mode_type} mode"
        log.error(msg)
        raise ValueError(msg)
