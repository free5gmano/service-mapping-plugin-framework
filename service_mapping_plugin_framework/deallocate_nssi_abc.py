import abc
import json
import requests

from service_mapping_plugin_framework import settings


class DeallocateNSSIabc(metaclass=abc.ABCMeta):
    def __init__(self, nm_host, nfvo_host, subscription_host, parameter):
        self.NM_URL = settings.NM_URL.format(nm_host)
        self.NFVO_URL = settings.NFVO_URL.format(nfvo_host)
        self.SUBSCRIPTION_HOST = settings.SUBSCRIPTION_HOST.format(subscription_host)
        self.ns_instance = str()
        self.ns_descriptor = str()
        self.vnf_package = list()
        self.vnfp_subscription = dict()
        self.nsd_subscription = str()
        self.nsi_subscription = str()
        self.parameter = parameter
        self.headers = {'Content-type': 'application/json'}

    def get_moi(self):
        # Get MOI Configure
        print('NSSI:', self.parameter['slice_instance'])
        # headers = {'Content-type': 'application/json', 'Connection': 'close'}
        scope = ["BASE_NTH_LEVEL", 1]
        url = self.NM_URL + 'NetworkSliceSubnet/{}/'.format(self.parameter['slice_instance'])
        payload = {'scope': str(scope)}
        moi = requests.get(url, params=payload, headers=self.headers)
        if moi.status_code in (200, 201):
            # Nsinfo assign
            print(moi.json())
            nsinfo = moi.json()['attributeListOut'][0]['nsInfo']
            self.ns_instance = nsinfo['id']
            self.ns_descriptor = nsinfo['nsdInfoId']
            self.vnf_package = eval(nsinfo['vnfInstance'])
            # monitor_parameter = eval(nsinfo['monitoringParameter'])
            # self.vnfp_subscription = monitor_parameter['vnfp_subscription']
            # self.nsd_subscription = monitor_parameter['nsd_subscription']
            # self.nsi_subscription = monitor_parameter['nsi_subscription']
        else:
            response = {
                "attributeListOut": {
                    'moi': 'Get NetworkSliceSubnet MOI Configure Failed'
                },
                "status": "OperationFailed"
            }
            raise Exception(response)

    def ns_termination(self):
        self.terminate_network_service_instance()
        self.delete_network_service_instance()
        # self.delete_network_service_instance_subscriptions()
        if self.parameter['mano_template']:
            self.update_network_service_descriptor()
            self.delete_network_service_descriptor()
            # self.delete_network_service_descriptor_subscriptions()
            self.nf_provisioning()

    def nf_provisioning(self):
        self.update_vnf_package()
        self.delete_vnf_package()
        # self.delete_vnf_package_subscriptions()

    @abc.abstractmethod
    def coordinate_tn_manager(self):
        return NotImplemented

    @abc.abstractmethod
    def terminate_network_service_instance(self):
        return NotImplemented

    @abc.abstractmethod
    def delete_network_service_instance(self):
        return NotImplemented

    @abc.abstractmethod
    def delete_network_service_instance_subscriptions(self):
        return NotImplemented

    @abc.abstractmethod
    def update_network_service_descriptor(self):
        return NotImplemented

    @abc.abstractmethod
    def delete_network_service_descriptor(self):
        return NotImplemented

    @abc.abstractmethod
    def delete_network_service_descriptor_subscriptions(self):
        return NotImplemented

    @abc.abstractmethod
    def update_vnf_package(self):
        return NotImplemented

    @abc.abstractmethod
    def delete_vnf_package(self):
        return NotImplemented

    @abc.abstractmethod
    def delete_vnf_package_subscriptions(self):
        return NotImplemented

    def update_moi(self):
        print('Update Slice moi...')
        url = self.NM_URL + "NetworkSliceSubnet/{}/".format(
            self.parameter['slice_instance'])
        payload = {'scope': '["BASE_NTH_LEVEL", 0]'}
        data = {
            "modificationList": [
                ["nsInfo", "operationalState", "administrativeState"],
                ["", "DISABLED", "UNLOCKED"],
                "REPLACE"
            ]
        }
        requests.patch(url, data=json.dumps(data), params=payload, headers=self.headers)
        self.delete_moi()

    def delete_moi(self):
        print('Delete NsInfo moi...')
        url = self.NM_URL + "NsInfo/{}/".format(self.parameter['slice_instance'])
        payload = {
            'scope': '["BASE_NTH_LEVEL", 0]'
        }
        response = requests.delete(url, params=payload, headers=self.headers)
        print(response.status_code)

    def deallocate_nssi(self):  # TODO: if use existing nssi
        self.get_moi()
        self.ns_termination()
        self.coordinate_tn_manager()
        self.update_moi()
