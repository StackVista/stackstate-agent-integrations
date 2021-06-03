import unittest
from .deployer.deployer import Deployer
import random
import string  # pylint: disable=deprecated-module
import os
import yaml
from botocore.exceptions import ClientError
import boto3
from botocore.config import Config
try:
    from pathlib import Path
except ImportError:
    from pathlib2 import Path


DEFAULT_BOTO3_RETRIES_COUNT = 50

DEFAULT_BOTO3_CONFIG = Config(
    retries=dict(
        max_attempts=DEFAULT_BOTO3_RETRIES_COUNT,
    )
)


class ClientProvider:
    def __init__(self, dir):
        self._cloudformation_client = None
        self._s3_client = None
        self._api_client = None
        self._lambda_client = None
        self._iam_client = None
        self._api_v2_client = None
        self._sfn_client = None

        with open(Path(dir, 'stackstate_checks/aws_topology.yaml'), 'r') as stream:
            data_loaded = yaml.safe_load(stream)

        self.external_id = "disable_external_id_this_is_unsafe"  # data_loaded["init_config"]["external_id"]
        self.aws_access_key_id = data_loaded["init_config"]["aws_access_key_id"]
        self.aws_secret_access_key = data_loaded["init_config"]["aws_secret_access_key"]
        self.role = "arn:aws:iam::548105126730:role/binx"  # data_loaded["instances"][0]["role_arn"]

        if self.aws_secret_access_key and self.aws_access_key_id:
            self.sts_client = boto3.client(
                'sts',
                config=DEFAULT_BOTO3_CONFIG,
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            )
        else:
            # Rely on credential provider chain to find credentials
            try:
                self.sts_client = boto3.client(
                    'sts',
                    config=DEFAULT_BOTO3_CONFIG
                )
            except Exception as e:
                raise Exception('No credentials found, the following exception was given: %s' % e)

    def get_session(self, region):
        try:
            # This should fail as it means it was able to successfully use the role without an external ID
            role = self.sts_client.assume_role(RoleArn=self.role, RoleSessionName='sts-agent-id-test')
            # This override should not be (publicly) documented
            if self.external_id != 'disable_external_id_this_is_unsafe':
                raise Exception(
                    'No external ID has been set for this role.' +
                    'For security reasons, please set the external ID.'
                )
        except ClientError as error:
            if error.response['Error']['Code'] == 'AccessDenied':
                try:
                    role = self.sts_client.assume_role(
                        RoleArn=self.role,
                        RoleSessionName='sts-agent-check-%s' % region,
                        ExternalId=self.external_id
                        )
                except Exception as error:
                    raise Exception('Unable to assume role %s. Error: %s' % (self.role, error))
            else:
                raise error

        self.session = boto3.Session(
            region_name=region if region != 'global' else 'us-east-1',
            aws_access_key_id=role['Credentials']['AccessKeyId'],
            aws_secret_access_key=role['Credentials']['SecretAccessKey'],
            aws_session_token=role['Credentials']['SessionToken']
        )
        return self.session

    @property
    def cfn_client(self):
        """
        Cloudformation Client
        """
        if not self._cloudformation_client:
            config = Config(retries={"max_attempts": 10, "mode": "standard"})
            self._cloudformation_client = self.session.client("cloudformation", config=config)
        return self._cloudformation_client


S3_BUCKET_PREFIX = "stackstate-integ-bucket-"
STACK_NAME_PREFIX = "stackstate-integ-stack-"

FILE_TO_S3_URI_MAP = {
    "code.zip": {"type": "s3", "uri": ""},
}

CODE_KEY_TO_FILE_MAP = {
    "codeuri": "code.zip",
}


# Length of the random suffix added at the end of the resources we create
# to avoid collisions between tests
RANDOM_SUFFIX_LENGTH = 12

def generate_suffix():
    """
    Generates a basic random string of length RANDOM_SUFFIX_LENGTH
    to append to objects names used in the tests to avoid collisions
    between tests runs
    Returns
    -------
    string
        Random lowercase alphanumeric string of length RANDOM_SUFFIX_LENGTH
    """
    return "".join(random.choice(string.ascii_lowercase) for i in range(RANDOM_SUFFIX_LENGTH))

class TestIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.FUNCTION_OUTPUT = "hello"
        cls.tests_integ_dir = Path(__file__).resolve().parents[1]
        cls.resources_dir = Path(cls.tests_integ_dir, "resources")
        cls.template_dir = Path(cls.resources_dir, "templates", "single")
        cls.output_dir = Path(cls.tests_integ_dir, "tmp")
        cls.expected_dir = Path(cls.resources_dir, "expected", "single")
        cls.code_dir = Path(cls.resources_dir, "code")
        cls.s3_bucket_name = S3_BUCKET_PREFIX + generate_suffix()
        cls.client_provider = ClientProvider(cls.tests_integ_dir)
        cls.session = cls.client_provider.get_session('eu-west-1')
        cls.my_region = cls.session.region_name
        cls.file_to_s3_uri_map = FILE_TO_S3_URI_MAP
        cls.code_key_to_file = CODE_KEY_TO_FILE_MAP

        if not cls.output_dir.exists():
            os.mkdir(str(cls.output_dir))

        # cls._upload_resources(FILE_TO_S3_URI_MAP)

    def create_and_verify_stack(self, file_name, parameters=None):
        """
        Creates the Cloud Formation stack and verifies it against the expected
        result
        Parameters
        ----------
        file_name : string
            Template file name
        parameters : list
            List of parameters
        """
        self.output_file_path = str(Path(self.tests_integ_dir, "tests/json/redshift/template.cfn.yaml"))
        self.stack_name = STACK_NAME_PREFIX + file_name.replace("_", "-") + "-" + generate_suffix()

        self.deploy_stack(parameters)

    def deploy_stack(self, parameters=None):
        """
        Deploys the current cloud formation stack
        """
        with open(self.output_file_path) as cfn_file:
            result, changeset_type = self.deployer.create_and_wait_for_changeset(
                stack_name=self.stack_name,
                cfn_template=cfn_file.read(),
                parameter_values=[] if parameters is None else parameters,
                capabilities=["CAPABILITY_IAM", "CAPABILITY_AUTO_EXPAND"],
                role_arn=None,
                notification_arns=[],
                s3_uploader=None,
                tags=[],
            )
            self.deployer.execute_changeset(result["Id"], self.stack_name)
            self.deployer.wait_for_execute(self.stack_name, changeset_type)

        self.stack_description = self.client_provider.cfn_client.describe_stacks(StackName=self.stack_name)
        self.stack_resources = self.client_provider.cfn_client.list_stack_resources(StackName=self.stack_name)

    def setUp(self):
        self.deployer = Deployer(self.client_provider.cfn_client)

    def tearDown(self):
        self.client_provider.cfn_client.delete_stack(StackName=self.stack_name)
        # if os.path.exists(self.output_file_path):
        #     os.remove(self.output_file_path)
        # if os.path.exists(self.sub_input_file_path):
        #     os.remove(self.sub_input_file_path)

    def xtest_integration(self):
        self.create_and_verify_stack("basic_http_api")
