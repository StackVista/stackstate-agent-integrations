from schematics import Model
from schematics.types import StringType, ModelType


class Location(Model):
    AwsRegion = StringType(required=True)
    AwsAccount = StringType(required=True)


class LocationInfo(Model):
    Location = ModelType(Location)

    def clone(self):
        return location_info(
            self.Location.AwsAccount,
            self.Location.AwsRegion
        )


def location_info(account_id, region):
    return LocationInfo(
        {
            'Location': {
                'AwsAccount': account_id,
                'AwsRegion': region
            }
        }
    )


def _tags_as_dictionary(lisf_of_tags, cap_flag=True):
    if lisf_of_tags and cap_flag:
        return dict((item['Key'], item['Value']) for item in lisf_of_tags)
    elif lisf_of_tags and not cap_flag:
        return dict((item['key'], item['value']) for item in lisf_of_tags)
    else:
        return {}


def correct_tags(data):
    if 'Tags' in data and isinstance(data['Tags'], list):
        data['Tags'] = _tags_as_dictionary(data['Tags'])
    if 'tags' in data and isinstance(data['tags'], list):
        data['Tags'] = _tags_as_dictionary(data['tags'], False)
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
