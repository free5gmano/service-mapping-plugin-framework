import abc


class DeallocateNSSIabc(metaclass=abc.ABCMeta):

    def __init__(self, nm_host, nfvo_host):
        pass

    def ns_termination(self):
        self.terminate_network_service_instance()
        self.delete_network_service_instance()
        self.update_network_service_descriptor()
        self.delete_network_service_descriptor()

    def nf_provisioning(self):
        self.update_vnf_package()
        self.delete_vnf_package()

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
    def update_network_service_descriptor(self):
        return NotImplemented

    @abc.abstractmethod
    def delete_network_service_descriptor(self):
        return NotImplemented

    @abc.abstractmethod
    def update_vnf_package(self):
        return NotImplemented

    @abc.abstractmethod
    def delete_vnf_package(self):
        return NotImplemented

    def deallocate_nssi(self):
        self.nf_provisioning()
        self.coordinate_tn_manager()
