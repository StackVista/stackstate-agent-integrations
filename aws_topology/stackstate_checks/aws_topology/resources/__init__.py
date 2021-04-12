from .registry import ResourceRegistry, RegisteredResourceCollector
from .s3 import S3_Collector  # noqa: F401
from .elb_v2 import ELB_V2_Collector  # noqa: F401
from .autoscaling import AutoScaling_Collector  # noqa: F401
from .api_gateway import ApiGateway_Stage_Collector  # noqa: F401
from .ec2_vpc import Vpc_Collector  # noqa: F401
from .ec2_vpn_gateway import VPN_Gateway_Collector  # noqa: F401
from .security_group import SecurityGroup_Collector  # noqa: F401
from .sns import SNS_Collector  # noqa: F401
from .firehose import Firehose_Collector  # noqa: F401
from .route53_domain import Route53_Domain_Collector  # noqa: F401
from .route53_hostedzone import Route53_HostedZone_Collector  # noqa: F401
from .kinesis import Kinesis_Collector  # noqa: F401
from .ec2 import EC2_Instance_Collector  # noqa: F401
from .redshift import Redshift_Collector  # noqa: F401
from .elb_classic import ELB_Classic_Collector  # noqa: F401
from .rds import RDS_Collector  # noqa: F401
from .lambdaf import Lambda_Collector  # noqa: F401
from .dynamodb import DynamoDB_Table_Collector  # noqa: F401
from .lambda_event_source_mapping import LambdaEventSourceMapping_Collector  # noqa: F401
from .ecs import ECS_Collector  # noqa: F401
from .cloudformation import CloudFormation_Collector  # noqa: F401
from .sqs import SQS_Collector  # noqa: F401

__all__ = [
    'ResourceRegistry',
    'RegisteredResourceCollector'
]
