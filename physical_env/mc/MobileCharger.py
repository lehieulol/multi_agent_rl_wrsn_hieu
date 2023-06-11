import numpy as np
from scipy.spatial.distance import euclidean
import copy

class MobileCharger:
    def __init__(self, location, mc_phy_spe):
        """
        The initialization for a MC.
        :param env: the time management system of this MC
        :param location: the initial coordinate of this MC, usually at the base station
        """
        self.env = None
        self.net = None
        self.id = None
        self.cur_phy_action = None
        self.location = np.array(location)
        self.energy = mc_phy_spe['capacity']
        self.capacity = mc_phy_spe['capacity']

        self.alpha = mc_phy_spe['alpha']
        self.beta = mc_phy_spe['beta']
        self.threshold = mc_phy_spe['threshold']
        self.velocity = mc_phy_spe['velocity']
        self.pm = mc_phy_spe['pm']
        self.chargingRate = 0
        self.chargingRange = mc_phy_spe['charging_range']
        self.epsilon = mc_phy_spe['epsilon']
        self.status = 1
        self.checkStatus()
        self.cur_action_type = "moving"

    def charge_step(self, nodes, t=1):
        """
        The charging process to nodes in 'nodes' within simulateTime
        :param nodes: the set of charging nodes
        :param t: the status of MC is updated every t(s)
        """
        for node in nodes:
            node.charger_connection(self)
        #print("MC " + str(self.id) + " Charging", self.location, self.energy, self.chargingRate)
        yield self.env.timeout(t)
        self.energy = self.energy - self.chargingRate * t
        self.cur_phy_action[2] = max(0, self.cur_phy_action[2] - t)
        for node in nodes:
            node.charger_disconnection(self)
        self.chargingRate = 0
        return

    def charge(self, chargingTime):
        tmp = chargingTime
        self.chargingTime = tmp
        nodes = []
        for node in self.net.listNodes:
            if euclidean(node.location, self.location) <= self.chargingRange:
                nodes.append(node)
        while True:
            span = min(tmp, 1.0)
            if self.chargingRate != 0:
                span = min(span, (self.energy - self.threshold) / self.chargingRate)
            yield self.env.process(self.charge_step(nodes, t=span))
            tmp -= span
            self.chargingTime = tmp
            self.checkStatus()
            if tmp == 0 or self.status == 0:
                break
        return

    def move_step(self, vector, t):
        yield self.env.timeout(t)
        self.location = self.location + vector
        self.energy -= self.pm * t * self.velocity
        

    def move(self, destination):
        moving_time = euclidean(destination, self.location) / self.velocity
        self.destination = destination
        self.movingTime = moving_time
        if moving_time == 0:
            return
        moving_vector = destination - self.location
        total_moving_time = moving_time
        while True:
            moving_time = euclidean(destination, self.location) / self.velocity
            self.movingTime = moving_time
            #print("MC " + str(self.id) + " Moving from", self.location, "to", destination)
            span = min(min(moving_time, 1.0), (self.energy - self.threshold) / (self.pm * self.velocity))
            yield self.env.process(self.move_step(moving_vector / total_moving_time * span, t=span))
            moving_time -= span
            if moving_time <= 0 or self.status == 0:
                break
        return

    def recharge(self):
        if euclidean(self.location, self.net.baseStation.location) <= self.epsilon:
            self.location = copy.deepcopy(self.net.baseStation.location)
            self.energy = self.capacity
        yield self.env.timeout(0)
    
    def operate_step(self, phy_action):
        #print("MC " + str(self.id), "phy_action", phy_action)
        destination = np.array([phy_action[0], phy_action[1]])
        chargingTime = phy_action[2]

        usedEnergy = euclidean(destination, self.location) * self.pm
        tmp = 0
        for node in self.net.listNodes:
            if euclidean(node.location, self.location) <= self.chargingRange and node.status == 1:
               tmp += self.alpha / (euclidean(self.location, node.location) + self.beta) ** 2
        usedEnergy += tmp * chargingTime
        usedEnergy += euclidean(destination, self.net.baseStation.location) * self.pm

        if usedEnergy > self.energy - self.threshold + self.capacity / 200.0:
            self.cur_phy_action = [self.net.baseStation.location[0], self.net.baseStation.location[1], 0]
            self.cur_action_type = "moving"
            yield self.env.process(self.move(destination=self.net.baseStation.location))
            yield self.env.process(self.recharge())
            return    
        self.cur_phy_action = phy_action
        self.cur_action_type = "moving"    
        yield self.env.process(self.move(destination=destination))
        self.cur_action_type = "charging"
        yield self.env.process(self.charge(chargingTime=chargingTime))

    def checkStatus(self):
        """
        check the status of MC
        """
        if self.energy <= self.threshold:
            self.status = 0
            self.energy = self.threshold
