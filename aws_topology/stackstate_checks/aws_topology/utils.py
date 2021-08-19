import gzip
import io
from schematics import Model
from schematics.types import StringType, ModelType
from datetime import datetime
import pytz
from six import PY2, string_types
import botocore


class Location(Model):
    AwsRegion = StringType(required=True)
    AwsAccount = StringType(required=True)


class LocationInfo(Model):
    Location = ModelType(Location)

    def clone(self):
        return location_info(self.Location.AwsAccount, self.Location.AwsRegion)


def location_info(account_id, region):
    return LocationInfo({"Location": {"AwsAccount": account_id, "AwsRegion": region}})


def _tags_as_dictionary(lisf_of_tags, cap_flag=True):
    if lisf_of_tags and cap_flag:
        return dict((item["Key"], item["Value"]) for item in lisf_of_tags)
    elif lisf_of_tags and not cap_flag:
        return dict((item["key"], item["value"]) for item in lisf_of_tags)
    else:
        return {}


def correct_tags(data):
    if "Tags" in data and isinstance(data["Tags"], list):
        data["Tags"] = _tags_as_dictionary(data["Tags"])
    if "tags" in data and isinstance(data["tags"], list):
        data["Tags"] = _tags_as_dictionary(data["tags"], False)
    return data


def capitalize_keys(in_dict):
    if type(in_dict) is dict:
        out_dict = {}
        for key, item in in_dict.items():
            if key == "Tags":
                out_dict[key] = item
            else:
                out_dict[key[:1].upper() + key[1:]] = capitalize_keys(item)
        return out_dict
    elif type(in_dict) is list:
        return [capitalize_keys(obj) for obj in in_dict]
    else:
        return in_dict


def seconds_ago(dt):
    return (datetime.utcnow().replace(tzinfo=pytz.utc) - dt).total_seconds()


def is_gz_file(body):
    with io.BytesIO(body) as test_f:
        return test_f.read(2) == b"\x1f\x8b"


def get_stream_from_s3body(body):
    if isinstance(body, string_types):
        # this case is only for test purposes
        if PY2:
            body = bytes(body)
        else:
            body = bytes(body, "ascii")
    elif isinstance(body, botocore.response.StreamingBody):
        body = body.read()
    if is_gz_file(body):
        return gzip.GzipFile(fileobj=io.BytesIO(body), mode="rb")
    else:
        return io.BytesIO(body)
