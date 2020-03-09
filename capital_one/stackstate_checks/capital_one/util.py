# A utility helper module for capital-one check


def create_resource_arn(resource, region, account_id, sub_resource, resource_id):
    return "arn:aws:{}:{}:{}:{}/{}".format(resource, region, account_id, sub_resource, resource_id)


def create_arn(resource, region, account_id, resource_id):
    return "arn:aws:{}:{}:{}:{}".format(resource, region, account_id, resource_id)
