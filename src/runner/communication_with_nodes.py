from configurator import NodesConfigurator

class NodesCommunicator:
    def __init__(self, mes_timeout_sec: float = 0.03):
        self.configurator = NodesConfigurator()
        self.configurator.find_nodes()
        self.mes_timeout = mes_timeout_sec

    def get_ice_nodes_states(self):
        for ice_node in self.configurator.ice_nodes:
            print(ice_node.recieve_message("", timeout_sec=self.mes_timeout))

    def get_mini_nodes_states(self):
        for mini_node in self.configurator.min_nodes:
            status = mini_node.get_esc_status(timeout_sec=self.mes_timeout)
            print(status.to_dict())

# TODO: add tests
# TODO: remove main
if __name__ == "__main__":
    communicator = NodesCommunicator(mes_timeout_sec=2.0)
    communicator.get_ice_nodes_states()
    communicator.get_mini_nodes_states()
