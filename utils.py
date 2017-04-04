import logging
from datetime import datetime
import time
from servicematcher.mappings import warehouse_category_id_level1_wizard


def get_logging(logger_name):
    logging.basicConfig()
    log = logging.getLogger(logger_name)
    log.setLevel(logging.INFO)
    return log


def get_unix_time():
    current_time = str(datetime.utcnow())
    ts, ms = current_time.split('.')
    dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
    return int(time.mktime(dt.timetuple()) * 1000) + int(ms[:3])


def get_wizard_for_wh(venue_category_id, wizard="", previous_match_wizard=""):
    """
    Merge the 2 wizards to the category where the 2 juniors agreed.
    "11111_22222_33333_44444_55555" and "11111_22222_33333_66666_55555" will return :
        "11111_22222_33333_00000_00000"
    if they disagree at level1, then it will return the venue_category_id wizard
    :param venue_category_id: int,
    :param wizard: str, if both not present then match to level1
    :param previous_match_wizard: str, if both not present then match to level1
    :return: wizard
    """
    if wizard[:5] != previous_match_wizard[:5]:
        return warehouse_category_id_level1_wizard[venue_category_id]
    for i in range(1, 5):
        j = 6 * ( i + 1 ) - 1
        if wizard[:j] != previous_match_wizard[:j]:
            wizard_for_wh = wizard[:j-6] + "_00000"*(5-i)
            return wizard_for_wh
    return wizard

