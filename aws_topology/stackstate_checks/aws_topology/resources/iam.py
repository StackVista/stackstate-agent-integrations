from .utils import make_valid_data, create_arn as arn
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType

"""
Doing an API:
Phase 0: analyse the API                                          4 hrs
Phase 1; create CloudFormation that uses all component/relations  8 hrs
Phase 2: emit main components + inter-relations                   2 hrs per component type
Phase 3: make external relations (from any/other component)       1 hr per relation
Phase 4: update stackpack visibility (icons + templates)          1 hr per component type
Phase 5: add health checks                                        1 hr per check
Phase 6: specify all telemetry metrics                            4 hrs per component type
Phase 7: cloudtrail events (for live updates)                     8 hrs per API
Phase 8: stackpack add actions (ie -> aws console)                1 hr per action

Resources to do:
mfa devices
virtual mfa devices
access keys

saml providers
ssh public keys
signing certificates
service specific credentials
server certificates
? policies granting service access ?
open id connect providers
account aliases
login profile
"""


def create_group_arn(region=None, account_id=None, resource_id=None, **kwargs):
    return arn(resource='iam', region='', account_id=account_id, resource_id='group/' + resource_id)


class User(Model):
    Arn = StringType(required=True)


class PolicyDocument(Model):
    PolicyName = StringType(required=True)


class PolicyAttachment(Model):
    PolicyArn = StringType(required=True)


class Boundary(Model):
    PermissionsBoundaryArn = StringType(required=True)


class Group(Model):
    Arn = StringType(required=True)


class Role(Model):
    Arn = StringType(required=True)


class Policy(Model):
    Arn = StringType(required=True)
    DefaultVersionId = StringType(required=True)


class InstanceProfile(Model):
    Arn = StringType(required=True)


class IAMProcessor(RegisteredResourceCollector):
    API = "iam"
    API_TYPE = "global"
    COMPONENT_TYPE = "aws.iam.user"
    CLOUDFORMATION_TYPE = 'AWS::IAM::User'

    def process_all(self, filter=None):
        # handle summary
        for page in self.client.get_paginator('get_account_authorization_details').paginate():
            if page:
                for user in page.get('UserDetailList', []):
                    self.process_user_details(user)
                for group in page.get('GroupDetailList', []):
                    self.process_group_details(group)
                for role in page.get('RoleDetailList', []):
                    self.process_role_details(role)
                for policy in page.get('Policies', []):
                    self.process_policy(policy)

    def process_policy_document(self, owner, policy):
        doc = PolicyDocument(policy, strict=False)
        doc.validate()
        output = make_valid_data(policy)
        policy_arn = owner.Arn + ':inlinepolicy/' + doc.PolicyName
        self.emit_component(policy_arn, 'aws.iam.policy', output)
        self.agent.relation(owner.Arn, policy_arn, 'has resource', {})

    def process_policy_attachment(self, owner, attachment):
        att = PolicyAttachment(attachment, strict=False)
        self.agent.relation(owner.Arn, att.PolicyArn, 'uses service', {})

    def process_boundary(self, owner, boundary):
        bound = Boundary(boundary, strict=False)
        bound.validate()
        self.agent.relation(owner.Arn, bound.PermissionsBoundaryArn, 'uses service', {})

    def process_user_details(self, user_detail):
        user_policies = user_detail.pop('UserPolicyList', [])
        attached_policies = user_detail.pop('AttachedManagedPolicies', [])
        groups = user_detail.pop('GroupList', [])
        boundary = user_detail.pop('PermissionsBoundary', {})
        user = User(user_detail, strict=False)
        user.validate()
        output = make_valid_data(user_detail)
        self.emit_component(user.Arn, 'aws.iam.user', output)
        for policy in user_policies:
            self.process_policy_document(user, policy)
        for attachment in attached_policies:
            self.process_policy_attachment(user, attachment)
        for group in groups:
            self.agent.relation(user.Arn, self.agent.create_arn(
                'AWS::IAM::Group',
                self.location_info,
                group
            ), 'uses service', {})
        if boundary:
            self.process_boundary(user, boundary)

    def process_group_details(self, group_detail):
        group_policies = group_detail.pop('GroupPolicyList', [])
        attached_policies = group_detail.pop('AttachedManagedPolicies', [])
        group = Group(group_detail, strict=False)
        group.validate()
        output = make_valid_data(group_detail)
        self.emit_component(group.Arn, 'aws.iam.group', output)
        for policy in group_policies:
            self.process_policy_document(group, policy)
        for attachment in attached_policies:
            self.process_policy_attachment(group, attachment)

    def process_instance_profile(self, role, data):
        roles = data.pop('Roles', [])
        profile = InstanceProfile(data, strict=False)
        profile.validate()
        output = make_valid_data(data)
        self.emit_component(profile.Arn, 'aws.iam.instance_profile', output)
        for role in roles:
            self.agent.relation(profile.Arn, role['Arn'], 'uses service', {})

    def process_role_details(self, role_detail):
        role_policies = role_detail.pop('RolePolicyList', [])
        attached_policies = role_detail.pop('AttachedManagedPolicies', [])
        instance_profiles = role_detail.pop('InstanceProfileList', [])
        boundary = role_detail.pop('PermissionsBoundary', {})
        role = Role(role_detail, strict=False)
        role.validate()
        output = make_valid_data(role_detail)
        self.emit_component(role.Arn, 'aws.iam.role', output)
        for policy in role_policies:
            self.process_policy_document(role, policy)
        for attachment in attached_policies:
            self.process_policy_attachment(role, attachment)
        if boundary:
            self.process_boundary(role, boundary)
        for profile in instance_profiles:
            self.process_instance_profile(role, profile)

    def process_policy(self, policy):
        versions = policy.pop('PolicyVersionList', [])
        pol = Policy(policy, strict=False)
        output = make_valid_data(policy)
        for version in versions:
            if version.get('VersionId') == pol.DefaultVersionId:
                output['Document'] = version.get('Document')
        self.emit_component(pol.Arn, 'aws.iam.policy', output)
