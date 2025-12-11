from typing import Sequence

def get_zone_indices(mapping: dict, zone_ids: Sequence[int]) -> Sequence[int]:
    """
    Reads the zone mapping from the given OMX file and converts a list of zone_ids to indices.

    Args:
        mapping (dict): Dictionary mapping zone IDs to their indices.
        zone_ids (Sequence[int]): List of zone IDs to convert.

    Returns:
        Sequence[int]: List of corresponding indices for the given zone IDs.
    """
    indices = []
    for zone_id in zone_ids:
        if zone_id > 0:
            indices.append(mapping.get(zone_id, -1))
        else:
            indices.append(zone_id)
    return indices