import logging
from scipy.interpolate import griddata
from numpy import linspace, meshgrid, reshape, array, argmax, delete

from utils import numpy_array_index
from copy import deepcopy, copy
from regressors import Regressor, GaussianProcessRegressor, GaussianProcessRegressor3

class CostModel(object):

    def __init__(self, configuration, controller, fitness):
        self.configuration = configuration
        self.controller = controller
        self.fitness = fitness
        self.was_trained = False
        self.total_cost = 0.0
        
    def train(self):
        raise NotImplementedError('CostModel is an abstract class, this '
                                  'should not be called.')
    def trained(self):
        return self.was_trained
                                  
    def predict(self, particles):
        raise NotImplementedError('CostModel is an abstract class, this '
                                  'should not be called.')
                                  
    def add_training_instance(self, part, cost):
        self.total_cost = cost + self.total_cost
        
    def contains_training_instance(self, part):
        pass    
        
    def get_training_instance(self, part):
        pass

    # def __getstate__(self):
       # Don't pickle fitness and configuration
        # d = dict(self.__dict__)
        # del d['configuration']
        # del d['fitness']
        # return d

    def contains_particle(self, part):
        pass
        
    def particle_value(self, part):
        pass
    
    def model_failed(self, part):
        pass
        
    def max_uncertainty(self):
        pass

    def get_state_dictionary(self):
        raise NotImplementedError('Trial is an abstract class, '
                                  'this should not be called.')
        
    def set_state_dictionary(self, dict):
        raise NotImplementedError('Trial is an abstract class, '
                                  'this should not be called.')
                                  
    def get_total_cost(self, dict):
        raise NotImplementedError('Trial is an abstract class, '
                                  'this should not be called.')    
                                  
    def get_copy(self):
        raise NotImplementedError('Trial is an abstract class, '
                                  'this should not be called.')
        
class DummyCostModel(CostModel):

    def predict(self, particles):
        MU, S2 = self.regressor.predict(particles)
        return MU

    def train(self):
        self.was_trained = True
        return True

    def model_particle(self, particle):
        return 0, 0, 0
        
    def contains_training_instance(self, part):
        return False

    def model_failed(self, part):
        return False
        
    def get_state_dictionary(self):
        return {"total_cost" : self.total_cost}
        
    def set_state_dictionary(self, dict):
        self.total_cost = dict["total_cost"]
        
    def get_copy(self):
        model = DummyCostModel(self.configuration, self.controller, self.fitness)
        model.set_state_dictionary(self.cost_model.get_state_dictionary())
        return model
        
class ProperCostModel(CostModel):

    def __init__(self, configuration, controller, fitness):
        super(ProperCostModel, self).__init__(configuration,controller,fitness)
        self.fitness = fitness
        #self.configuration = deepcopy(self.configuration)
        #self.configuration.corr = "isotropic"
        #self.configuration.random_start = 10
        self.soft_regressor = GaussianProcessRegressor3(controller, configuration)
        self.hard_regressor = GaussianProcessRegressor3(controller, configuration)
                
    def no_software_param(self):
        software_axis = [i for i, dimension in enumerate(self.fitness.designSpace) if dimension["set"] == "s"]
        return software_axis == []
                
    def get_copy(self):
        model = ProperCostModel(self.configuration, self.controller, self.fitness)
        model.set_state_dictionary(self.get_state_dictionary())
        return model
        
    def predict(self, part):
        hard = 0.0
        soft = 0.0
        if not self.bitstream_was_generated(part):
            hard, S2, EI, P = self.hard_regressor.predict(array([part]))
        if not self.no_software_param():
            soft, S2, EI, P = self.soft_regressor.predict(array([part]))
        ## prediction has to be corrected for software models
        #logging.debug(str(hard + soft))
        return hard + soft
        
    def predict_raw(self, part):
        hard, S2, EI, P = self.hard_regressor.predict(array([part]))
        soft = 0.0
        if not self.no_software_param():
            soft, S2, EI, P = self.soft_regressor.predict(array([part]))
        ## prediction has to be corrected for software models
        #logging.debug(str(hard + soft))
        return hard + soft
                
    def train(self):
        logging.info("Training Cost Model")
        if self.no_software_param():
            soft_trained = True
        else:
            soft_trained = self.soft_regressor.train()
        self.was_trained = soft_trained and self.hard_regressor.train() 
        if self.was_trained:
            logging.info("Training Cost Model OK")
        else:
            logging.info("Training Cost Model Failed")
        return self.was_trained
        
    def add_training_instance(self, part, cost):
        if self.bitstream_was_generated(part):
            self.soft_regressor.add_training_instance(part, cost)
        else:
            try:
                software_c_prediction = self.soft_regressor.predict(array([part]))[0][0][0] ## we ignore s2
            except:
                logging.info("Software has not been evaluted yet, using assumption that hardware cost >> software cost")
                software_c_prediction = 0.0
            self.hard_regressor.add_training_instance(part, cost - software_c_prediction)
                
                
    def contains_training_instance(self, part):
        return self.hard_regressor.contains_training_instance(part) or  self.soft_regressor.contains_training_instance(part)

    def bitstream_was_generated(self, part):
        software_axis = [i for i, dimension in enumerate(self.fitness.designSpace) if dimension["set"] == "s"]
        pruned_training_set = delete(self.hard_regressor.get_training_set(),software_axis,1)
        pruned_part = delete([part],software_axis,1)
        contains, index = numpy_array_index(pruned_training_set, pruned_part[0])
        return contains
        
    def get_training_instance(self, part):
        cost = 0.0
        if self.hard_regressor.contains_training_instance(part):
            cost = self.hard_regressor.get_training_instance(part)
        if self.soft_regressor.contains_training_instance(part):
            cost = cost + self.soft_regressor.get_training_instance(part)
        return cost
        
    def model_failed(self, part):
        return False

    def get_state_dictionary(self):
        return {"soft_regressor_state_dict" : self.soft_regressor.get_state_dictionary(),
                "hard_regressor_state_dict" : self.hard_regressor.get_state_dictionary()}
        
    def set_state_dictionary(self, dict):
        self.soft_regressor.set_state_dictionary(dict["soft_regressor_state_dict"])
        self.hard_regressor.set_state_dictionary(dict["hard_regressor_state_dict"])
