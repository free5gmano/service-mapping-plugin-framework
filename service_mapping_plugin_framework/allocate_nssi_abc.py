import abc
import json
import os
import requests

from service_mapping_plugin_framework import settings


class AllocateNSSIabc(metaclass=abc.ABCMeta):

    def __init__(self, nm_host, nfvo_host, subscription_host, parameter):
        self.NM_URL = settings.NM_URL.format(nm_host)
        self.NFVO_URL = settings.NFVO_URL.format(nfvo_host)
        self.SUBSCRIPTION_HOST = settings.SUBSCRIPTION_HOST.format(subscription_host)
        self.nsinfo = dict()
        self.nssiId = str()
        self.content = dict()
        self.moi_config = dict()
        self.parameter = parameter

    def get_nsst(self):
        print(os.path.join(settings.DATA_PATH, 'NRM', self.parameter['slice_template']))
        for root, directory, file in os.walk(os.path.join(settings.DATA_PATH,
                                                          'NRM', self.parameter['slice_template'])):
            # Assign sliceNrm.json attribute
            with open(os.path.join(root, file[0])) as f:
                self.content = json.loads(f.read())

    def check_feasibility(self):
        headers = {'Content-type': 'application/json'}
        url = self.NM_URL + 'GenericTemplate/{}'.format(
            self.parameter['vnf_template'])
        generic_template = requests.get(url, headers=headers)
        moi = self.get_moi()
        ns_instance_id = moi.json()['attributeListOut'][0]['nsInfo']['id']
        ns_instance = self.read_ns_instantiation(ns_instance_id)
        vnf_list = dict()
        vnf_instance_list = dict()
        vnf_add_list = dict()
        vnf_delete_list = dict()
        vnf_scale_list = dict()

        for element in generic_template.json()['content']:
            vnf_config = eval(element['topology_template'])
            descriptor_id = vnf_config['node_templates']['VNF1']['properties']['descriptor_id']
            product_name = vnf_config['node_templates']['VNF1']['properties']['product_name']
            replicas = vnf_config['node_templates']['VDU1']['attributes']['replicas']

            # vnf_list = {'vnfd ID': ['vnf product name', 'vnf instance replicas']}
            vnf_list[descriptor_id] = [product_name.lower(), replicas]

        for vnf_instance in ns_instance.json()['vnfInstance']:
            # vnf_instance_list = {'vnfd ID': ['vnf product name', 'vnf instance id']}
            vnf_instance_list[vnf_instance['vnfdId']] = [vnf_instance['vnfProductName'],
                                                         vnf_instance['id']]
        for element in vnf_list:
            if element not in vnf_instance_list:
                vnf_add_list[element] = vnf_list[element]
            else:
                vnf_scale_list[element] = vnf_list[element]

        for element in vnf_instance_list:
            if element not in vnf_list:
                vnf_delete_list[element] = vnf_instance_list[element]
            else:
                # {'vnfd ID': ['vnf product name', 'vnf instance replicas', 'vnf instance id']}
                vnf_scale_list[element].append(vnf_instance_list[element][1])

        path = os.path.join(settings.DATA_PATH, 'VNF', self.parameter['vnf_template'])
        if vnf_add_list:
            for vnfd in vnf_add_list:
                vnf_pkg_path = os.path.join(path, vnf_add_list[vnfd][0])
                moi_config = ""
                self.create_vnf_package(moi_config)
                self.upload_vnf_package(vnf_pkg_path)
                # Using vnf package id replace vnf instance id
                update_info = {'type': 'ADD_VNF', "vnf_instance_id": self.vnf_pkg_id}
                self.update_ns_instantiation(ns_instance_id, update_info)

        if vnf_delete_list:
            for vnf in vnf_delete_list:
                update_info = {'type': 'REMOVE_VNF', "vnf_instance_id": vnf_delete_list[vnf][1]}
                self.update_ns_instantiation(ns_instance_id, update_info)

        if vnf_scale_list:
            for vnf in vnf_scale_list:
                scale_info = {'type': "SCALE_OUT",
                              "vnf_instance_id": vnf_scale_list[vnf][2],
                              "replicas": vnf_scale_list[vnf][1]}
                print(scale_info)
                self.scale_ns_instantiation(ns_instance_id, scale_info)

        self.read_ns_instantiation(ns_instance_id)
        self.nssiId = self.parameter['use_existed']

    def create_moi(self):
        content = self.content
        nm_url = self.NM_URL
        headers = {'Content-type': 'application/json', 'Connection': 'close'}

        def sst():
            # Create SST MOI
            print('Create SST MOI')

            content_snssai = content['definitions']['SnssaiList']
            sst_value = content_snssai['sst']['value']
            url = nm_url + "SST/*/"
            scope = ["BASE_NTH_LEVEL", 0]
            payload = {'scope': str(scope),
                       'filter': "value='{}'".format(sst_value)}
            moi = requests.get(url, params=payload, headers=headers)
            if moi.json()['attributeListOut'].__len__() == 0:
                data = {
                    "attributeListIn": {
                        "value": sst_value,
                        "type": content_snssai['sst']['type'],
                        "characteristics": content_snssai['sst']['characteristics']
                    }
                }
                moi = requests.put(url, data=json.dumps(data), headers=headers)
                if moi.status_code in (200, 201):
                    return moi.json()['attributeListOut']
                else:
                    response = {
                        "attributeListOut": {
                            'moi': 'Create SST Failed'
                        },
                        "status": "OperationFailed"
                    }
                    raise Exception(response)

        def snssai():
            # Create SNSSAIList MOI
            print('Create SNSSAIList MOI')
            url = nm_url + "SNSSAIList/*/"
            data = {
                "attributeListIn": {
                    "sST": [content['definitions']['SnssaiList']['sst']['value']],
                    "sD": content['definitions']['SnssaiList']['sd']
                }
            }
            moi = requests.put(url, data=json.dumps(data), headers=headers)
            if moi.status_code in (200, 201):
                return moi.json()['attributeListOut']
            else:
                response = {
                    "attributeListOut": {
                        'moi': 'Create SNSSAI Failed'
                    },
                    "status": "OperationFailed"
                }
                raise Exception(response)

        def plmnid():
            # Create PLMNIdList MOI
            print('Create PLMNIdList MOI')
            content_plmnid = content['definitions']['PlmnIdList']
            url = nm_url + "PLMNIdList/*/"
            scope = ["BASE_NTH_LEVEL", 0]
            payload = {'scope': str(scope),
                       'filter': "pLMNId='{}'".format(
                           content_plmnid['mcc'] + content_plmnid['mnc'])}
            moi = requests.get(url, params=payload, headers=headers)
            if moi.json()['attributeListOut'].__len__() == 0:
                data = {
                    "attributeListIn": {
                        "pLMNId": content_plmnid['mcc'] + content_plmnid['mnc'],
                        "mcc": content_plmnid['mcc'],
                        "mnc": content_plmnid['mnc'],
                        "MobileNetworkOperator": content_plmnid['operator']
                    }
                }
                moi = requests.put(url, data=json.dumps(data), headers=headers)
                print(moi.json())
                if moi.status_code in (200, 201):
                    return moi.json()['attributeListOut']
                else:
                    response = {
                        "attributeListOut": {
                            'moi': 'Create pLMNId Failed'
                        },
                        "status": "OperationFailed"
                    }
                    raise Exception(response)
            else:
                return moi.json()['attributeListOut'][0]

        def perfreq():
            # Create PerfRequirements MOI
            content_perfreq = content['definitions']['PrefReq']['properties']
            print('Create PerfRequirements MOI')
            url = nm_url + "PerfRequirements/*/"
            data = {
                "attributeListIn": {
                    "scenario": content_perfreq['scenario'],
                    "experiencedDataRateDL": content_perfreq['expDataRateDL'],
                    "experiencedDataRateUL": content_perfreq['expDataRateUL'],
                    "areaTrafficCapacityDL": content_perfreq['areaTrafficCapDL'],
                    "areaTrafficCapacityUL": content_perfreq['areaTrafficCapUL'],
                    "overallUserDensity": content_perfreq['userDensity'],
                    "activityFactor": content_perfreq['activityFactor'],
                    "ueSpeed": content_perfreq['uESpeed'],
                    "coverage": content_perfreq['coverage']
                }
            }
            moi = requests.put(url, data=json.dumps(data), headers=headers)
            if moi.status_code in (200, 201):
                return moi.json()['attributeListOut']
            else:
                response = {
                    "attributeListOut": {
                        'moi': 'Create PerfRequirements Failed'
                    },
                    "status": "OperationFailed"
                }
                raise Exception(response)

        def slice_profile(**kwargs):
            # Create SliceProfileList MOI
            print('Create SliceProfileList MOI')
            url = nm_url + "SliceProfileList/*/"
            data = {
                "attributeListIn": {
                    "sNSSAIListId": [kwargs['snssai']['id']],
                    "pLMNIdList": [kwargs['plmnid']['pLMNId']],
                    "perfReqId": [kwargs['perfreq']['id']]
                }
            }
            print(data)
            moi = requests.put(url, data=json.dumps(data), headers=headers)
            # print(moi.json())
            if moi.status_code in (200, 201):
                return moi.json()['attributeListOut']
            else:
                response = {
                    "attributeListOut": {
                        'moi': 'Create SliceProfileList Failed'
                    },
                    "status": "OperationFailed"
                }
                raise Exception(response)

        def slice_subnet(**kwargs):
            # Create NetworkSliceSubnet MOI
            print('Create NetworkSliceSubnet MOI ...')
            url = nm_url + 'NetworkSliceSubnet/*/'
            properties = content['definitions']['networkSliceSubnet']['properties']
            data = {
                "referenceObjectInstance": "",
                "attributeListIn": {
                    "mFIdList": "400852ba257e49508afb819c0444b2c",
                    "constituentNSSIIdList": properties['constituentNSSIIdList'],
                    "operationalState": properties['operationalState'],
                    "administrativeState": properties['administrativeState'],
                    "nsInfo": properties['nsInfo'],
                    "sliceProfileList": [kwargs['profile']['id']]
                }
            }
            moi = requests.put(url, data=json.dumps(data), headers=headers)
            if moi.status_code in (200, 201):
                return moi
            else:
                response = {
                    "attributeListOut": {
                        'moi': 'Create NetworkSliceSubnet Failed'
                    },
                    "status": "OperationFailed"
                }
                raise Exception(response)

        def moi_config(**kwargs):
            # Get MOI Configure
            print('NSSI:', kwargs['nssiId'])
            scope = ["BASE_NTH_LEVEL", 3]
            url = nm_url + 'NetworkSliceSubnet/{}/'.format(kwargs['nssiId'])
            payload = {'scope': str(scope),
                       'filter': "nssiId='{}'".format(kwargs['nssiId'])}
            moi = requests.get(url, params=payload, headers=headers)
            if moi.status_code in (200, 201):
                return moi
            else:
                response = {
                    "attributeListOut": {
                        'moi': 'Get NetworkSliceSubnet MOI Configure Failed'
                    },
                    "status": "OperationFailed"
                }
                raise Exception(response)

        sst()
        nssi = slice_subnet(profile=slice_profile(snssai=snssai(),
                                                  plmnid=plmnid(),
                                                  perfreq=perfreq()))
        self.nssiId = nssi.json()['attributeListOut']['nssiId'].replace('-', '')
        config = moi_config(nssiId=self.nssiId)
        self.moi_config = config.json()['attributeListOut'][0]

    def get_moi(self):
        # Get MOI Configure
        print('NSSI:', self.parameter['use_existed'])
        headers = {'Content-type': 'application/json', 'Connection': 'close'}
        scope = ["BASE_NTH_LEVEL", 1]
        url = self.NM_URL + 'NetworkSliceSubnet/{}/'.format(self.parameter['use_existed'])
        payload = {'scope': str(scope)}
        moi = requests.get(url, params=payload, headers=headers)
        if moi.status_code in (200, 201):
            return moi
        else:
            response = {
                "attributeListOut": {
                    'moi': 'Get NetworkSliceSubnet MOI Configure Failed'
                },
                "status": "OperationFailed"
            }
            raise Exception(response)

    def nf_provisioning(self):
        for root, directory, file in os.walk(
                os.path.join(settings.DATA_PATH, 'VNF', self.parameter['vnf_template'])):
            for vnf in directory:
                vnf_pkg_path = os.path.join(root, vnf)

                # Call os_ma_nfvo
                self.create_vnf_package(self.moi_config)
                # self.create_vnf_package_subscriptions(vnf)
                self.upload_vnf_package(vnf_pkg_path)
                # TODO gitlab feature/deallocateNSSI API in 250 row
                # self.listen_on_vnf_package_subscriptions()
            break

    def ns_instance_instantiation(self):
        for root, directory, file in os.walk(
                os.path.join(settings.DATA_PATH, 'NSD', self.parameter['ns_template'])):
            ns_des = self.parameter['ns_template']
            ns_descriptor_path = root

            self.create_ns_descriptor()
            # self.create_ns_descriptor_subscriptions(ns_des)
            self.upload_ns_descriptor(ns_descriptor_path)
            # self.listen_on_ns_descriptor_subscriptions()
            self.create_ns_instance()
            # self.create_ns_instance_subscriptions()
            self.ns_instantiation(ns_descriptor_path)
            # self.listen_on_ns_instance_subscriptions()
            break

    @abc.abstractmethod
    def coordinate_tn_manager(self):
        return NotImplemented

    @abc.abstractmethod
    def create_vnf_package(self, moi_config):
        return NotImplemented

    @abc.abstractmethod
    def upload_vnf_package(self, vnf_pkg_path):
        return NotImplemented

    @abc.abstractmethod
    def read_vnf_package(self, vnf_pkg_id):
        return NotImplemented

    @abc.abstractmethod
    def create_ns_descriptor(self):
        return NotImplemented

    @abc.abstractmethod
    def upload_ns_descriptor(self, ns_descriptor_path):
        return NotImplemented

    @abc.abstractmethod
    def read_ns_descriptor(self, nsd_object_id):
        return NotImplemented

    @abc.abstractmethod
    def create_ns_instance(self):
        return NotImplemented

    @abc.abstractmethod
    def read_ns_instantiation(self, ns_instance_id):
        return NotImplemented

    @abc.abstractmethod
    def update_ns_instantiation(self, ns_instance_id, update_info):
        return NotImplemented

    @abc.abstractmethod
    def ns_instantiation(self, ns_descriptor_path):
        # Should be assign 'nsinfo' parameter
        return NotImplemented

    @abc.abstractmethod
    def scale_ns_instantiation(self, ns_instance_id, scale_info):
        # Should be assign 'nsinfo' parameter
        return NotImplemented

    @abc.abstractmethod
    def create_vnf_package_subscriptions(self, vnf):
        return NotImplemented

    @abc.abstractmethod
    def create_ns_descriptor_subscriptions(self, ns_des):
        return NotImplemented

    @abc.abstractmethod
    def create_ns_instance_subscriptions(self):
        return NotImplemented

    @abc.abstractmethod
    def listen_on_vnf_package_subscriptions(self):
        return NotImplemented

    @abc.abstractmethod
    def listen_on_ns_descriptor_subscriptions(self):
        return NotImplemented

    @abc.abstractmethod
    def listen_on_ns_instance_subscriptions(self):
        return NotImplemented

    def update_moi(self):
        if self.parameter['use_existed']:
            # Update NsInfo MOI
            print('Update NsInfo moi...')
            url = self.NM_URL + "NsInfo/{}/".format(self.nsinfo['id'])
            payload = {'scope': '["BASE_NTH_LEVEL", 0]'}
            data = {
                "modificationList": [
                    ["nsInstanceName",
                     "nsInstanceDescription",
                     "nsdId",
                     "nsdInfoId",
                     "flavourId",
                     "vnfInstance",
                     "vnffgInfo",
                     "nestedNsInstanceId",
                     "nsState",
                     "_links"],
                    [self.nsinfo['nsInstanceName'],
                     self.nsinfo['nsInstanceDescription'],
                     self.nsinfo['nsdId'],
                     self.nsinfo['nsdInfoId'],
                     self.nsinfo['flavourId'],
                     self.nsinfo['vnfInstance'],
                     self.nsinfo['vnffgInfo'],
                     self.nsinfo['nestedNsInstanceId'],
                     self.nsinfo['nsState'],
                     self.nsinfo['_links']],
                    "REPLACE"
                ]
            }
            requests.patch(url, data=json.dumps(data), params=payload, headers=settings.HEADERS)
        else:
            # Create NsInfo MOI
            url = self.NM_URL + "NsInfo/*/"
            data = {
                "referenceObjectInstance": "",
                "attributeListIn": self.nsinfo
            }
            print(data)
            create_nsinfo_moi = requests.put(url, data=json.dumps(data), headers=settings.HEADERS)
            print('Create NsInfo moi status: {}'.format(create_nsinfo_moi.status_code))

            # Modify Slice MOI
            url = self.NM_URL + "NetworkSliceSubnet/{}/".format(self.nssiId)
            scope = ["BASE_NTH_LEVEL", 0]
            data = {
                "modificationList": [
                    [
                        "nsInfo"
                    ],
                    [
                        self.nsinfo['id']
                    ],
                    "REPLACE"
                ]
            }
            payload = {'scope': str(scope)}
            modify_moi = requests.patch(url, data=json.dumps(data),
                                        params=payload, headers=settings.HEADERS)
            print("Modify MOI status: {}".format(modify_moi.status_code))

        # Reorganization Slice Response
        scope = ["BASE_NTH_LEVEL", 2]
        payload = {'scope': str(scope)}
        url = self.NM_URL + "NetworkSliceSubnet/{}/".format(self.nssiId)
        get_moi = requests.get(url, params=payload, headers=settings.HEADERS)
        self.moi_config = get_moi.json()
        self.moi_config['nSSIId'] = \
            self.moi_config['attributeListOut'][0].pop('nssiId')
        if self.moi_config['attributeListOut'][0]['nsInfo']['vnfInstance']:
            self.moi_config['attributeListOut'][0]['nsInfo']['vnfInstance'] = \
                eval(self.moi_config['attributeListOut'][0]['nsInfo']['vnfInstance'])
        if self.moi_config['attributeListOut'][0]['nsInfo']['vnffgInfo']:
            self.moi_config['attributeListOut'][0]['nsInfo']['vnffgInfo'] = \
                eval(self.moi_config['attributeListOut'][0]['nsInfo']['vnffgInfo'])
        if self.moi_config['attributeListOut'][0]['nsInfo']['nestedNsInstanceId']:
            self.moi_config['attributeListOut'][0]['nsInfo']['nestedNsInstanceId'] = \
                eval(self.moi_config['attributeListOut'][0]['nsInfo']['nestedNsInstanceId'])
        if self.moi_config['attributeListOut'][0]['nsInfo']['_links']:
            self.moi_config['attributeListOut'][0]['nsInfo']['_links'] = \
                eval(self.moi_config['attributeListOut'][0]['nsInfo']['_links'])
        print("Slice MOI:", self.moi_config)

    def allocate_nssi(self):
        self.get_nsst()
        if self.parameter['use_existed']:
            print('Modify procedure...')
            self.check_feasibility()
            self.update_moi()
        else:
            print('Create procedure...')
            self.create_moi()
            self.nf_provisioning()
            self.ns_instance_instantiation()
            self.coordinate_tn_manager()
            self.update_moi()
