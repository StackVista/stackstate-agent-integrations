from .registry import ResourceRegistry, RegisteredResourceCollector
from .s3 import S3Collector  # noqa: F401
from .elb_v2 import ElbV2Collector  # noqa: F401
from .autoscaling import AutoscalingCollector  # noqa: F401
from .api_gateway import ApigatewayStageCollector  # noqa: F401
from .ec2_vpc import VpcCollector  # noqa: F401
from .ec2_vpn_gateway import VpnGatewayCollector  # noqa: F401
from .security_group import SecuritygroupCollector  # noqa: F401
from .sns import SnsCollector  # noqa: F401
from .firehose import FirehoseCollector  # noqa: F401
from .route53_domain import Route53DomainCollector  # noqa: F401
from .route53_hostedzone import Route53HostedzoneCollector  # noqa: F401
from .kinesis import KinesisCollector  # noqa: F401
from .ec2 import Ec2InstanceCollector  # noqa: F401
from .redshift import RedshiftCollector  # noqa: F401
from .elb_classic import ElbClassicCollector  # noqa: F401
from .rds import RdsCollector  # noqa: F401
from .lambdaf import LambdaCollector  # noqa: F401
from .dynamodb import DynamodbTableCollector  # noqa: F401
from .lambda_event_source_mapping import LambdaeventsourcemappingCollector  # noqa: F401
from .ecs import EcsCollector  # noqa: F401
from .cloudformation import CloudformationCollector  # noqa: F401
from .sqs import SqsCollector  # noqa: F401

__all__ = [
    'ResourceRegistry',
    'RegisteredResourceCollector'
]
