
from .utils import make_valid_data, create_arn as arn, set_required_access_v2, client_array_operation
from .registry import RegisteredResourceCollector
from schematics import Model
from schematics.types import StringType
from collections import namedtuple


class Certificate(Model):
    DomainName = StringType(required=True)
    CertificateArn = StringType(required=True)


CertificateData = namedtuple('CertificateData', ['description', 'tags'])


class ACMProcessor(RegisteredResourceCollector):
    API = "acm"
    API_TYPE = "regional"
    COMPONENT_TYPE = "aws.acm.certificate"
    CLOUDFORMATION_TYPE = 'AWS::CertificateManager::Certificate'

    @set_required_access_v2("acm:DescribeCertificate")
    def collect_certificate_description(self, arn):
        return self.client.describe_certificate(CertificateArn=arn)

    @set_required_access_v2("acm:ListTagsForCertificate")
    def collect_tags_for_certificate(self, arn):
        return self.client.list_tags_for_certificate(CertificateArn=arn).get('Tags')

    def collect_certificate(self, summary):
        arn = summary.get('CertificateArn')
        description = self.collect_certificate_description(arn) or summary
        tags = self.collect_tags_for_certificate(arn) or []
        return CertificateData(description=description, tags=tags)

    def collect_certificates(self):
        for certificate in [
                self.collect_certificate(certificate_summary) for certificate_summary in client_array_operation(
                    self.client,
                    'list_certificates',
                    'CertificateSummaryList',
                    Includes={
                        'keyType': ['RSA_2048,RSA_1024,RSA_4096,EC_prime256v1,EC_secp384r1,EC_secp521r1']
                    }
                )
        ]:
            yield certificate        

    def process_all(self, filter=None):
        self.process_certificates()

    @set_required_access_v2("acm:ListCertificates")
    def process_certificates(self):
        for certificate in collect_certificates():
            process_certificate(certificate)
    
    def process_certificate(self, data):
        output = make_valid_data(data.description)
        certificate = Certificate(data.description, strict=False)
        certificate.validate()
        output['Tags'] = data.tags
        output["Name"] = certificate.DomainName
        self.emit_component(certificate.CertificateArn, 'aws.acm.certificate', output)
