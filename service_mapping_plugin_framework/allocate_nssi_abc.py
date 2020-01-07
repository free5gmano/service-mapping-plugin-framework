import abc
import os
from optparse import OptionParser

from service_mapping_plugin_framework import settings


class AllocateNSSIabc(metaclass=abc.ABCMeta):

    def __init__(self, nm_host, nfvo_host):
        self.NM_URL = settings.NM_URL.format(nm_host)
        self.NFVO_URL = settings.NFVO_URL.format(nfvo_host)

        parser = OptionParser()
        parser.add_option("-v", "--vnf-package-template", help="VNF Package Template Path")
        parser.add_option("-n", "--ns-template", help="Network Service Template Path")
        (options, args) = parser.parse_args()
        self.vnf_package_template_path = options.vnf_package_template
        self.ns_template_path = options.ns_template

    def nf_provisioning(self):
        for root, directory, file in os.walk(self.vnf_package_template_path):
            for vnf in directory:
                vnf_package_path = os.path.join(root, vnf)

                # os_ma_nfvo interface API
                self.create_vnf_package(vnf_package_path)
                self.upload_vnf_package(vnf_package_path)
            break

    def ns_instance_instantiation(self):
        # os_ma_nfvo interface API
        self.create_ns_descriptor(self.ns_template_path)
        self.upload_ns_descriptor(self.ns_template_path)
        self.create_ns_instance(self.ns_template_path)
        self.ns_instantiation(self.ns_template_path)

    @abc.abstractmethod
    def create_vnf_package(self, vnf_package_path):
        return NotImplemented

    @abc.abstractmethod
    def upload_vnf_package(self, vnf_package_path):
        return NotImplemented

    @abc.abstractmethod
    def create_ns_descriptor(self, ns_descriptor_path):
        return NotImplemented

    @abc.abstractmethod
    def upload_ns_descriptor(self, ns_descriptor_path):
        return NotImplemented

    @abc.abstractmethod
    def create_ns_instance(self, ns_descriptor_path):
        return NotImplemented

    @abc.abstractmethod
    def ns_instantiation(self, ns_descriptor_path):
        return NotImplemented

    def allocate_nssi(self):
        self.nf_provisioning()
        self.ns_instance_instantiation()
