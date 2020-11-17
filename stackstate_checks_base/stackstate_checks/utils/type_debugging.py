import logging

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(message)s')


def print_type(parent, value):
    types_summary = []
    _print_type(parent, value, types_summary)
    output = '\n'.join(types_summary)
    logging.debug(output)
    return output


def _print_type(parent, value, types_summary):
    types_summary.append("key: %s, type: %s" % (parent, type(value)))
    if isinstance(value, dict):
        for k, value in value.items():
            _print_type(k, value, types_summary)
    elif isinstance(value, list):
        for list_item in value:
            _print_type(parent, list_item, types_summary)
