import logging
import os
import sys
from threading import Thread
from time import strftime
import io
import pickle 

from utils import load_script, get_trial_constructor


class Run(object):

    def __init__(self, name, fitness, configuration, controller):
        self.trials = []
        self.fitness = fitness
        self.configuration = configuration
        self.controller = controller
        fitness_file_name = None
        configuration_file_name = None
        trial_type = None
        if fitness:
            fitness_file_name = os.path.abspath(self.fitness.__file__)
            if fitness_file_name[-1] == 'c':  # .pyc
                fitness_file_name = fitness_file_name[:-1]
        if configuration:
            configuration_file_name = os.path.abspath(
                self.configuration.__file__)
            if configuration_file_name[-1] == 'c':  # .pyc
                configuration_file_name = configuration_file_name[:-1]
            trial_type = configuration.trials_type
        self.state_dictionary = {"fitness_file_name": fitness_file_name,
                                 "configuration_file_name" : configuration_file_name,
                                 "name" : name,
                                 "wait" : False,
                                 "status" : "Running",
                                 "trial_type" : trial_type
                                 }
                                 
        if configuration:
            self.set_no_of_trials(configuration.trials_count)
        
    def run(self):
        self.controller.register_run(self)
        # Initialise results folder
        now = strftime('%Y-%m-%d_%H-%M-%S')
        self.results_folder_path = '{}/{}'.format(
            self.configuration.results_folder_path, now)
        
        # Initialise trials
        for trial_no in range(0, self.get_no_of_trials()):
            trial = self.get_trial_type_constructor()(trial_no, self.get_name(), self.fitness,
                          self.configuration, self.controller,
                          self.results_folder_path)
            if trial.initialise():
                self.trials.append(trial)
            
        self.save()

        # Run trials
        for trial in self.trials:
            trial.daemon = True
            trial.start()

    ## TODO - this has to be changed... its just that ctrl+c wont be propagated otherwise...
    
    def join(self):
        for trial in self.trials:
            trial.join(100000000)

    def load(self):
        logging.info('Loading the Run')
        try:
            with open(self.get_run_file(), 'rb') as outfile:
               dict = pickle.load(outfile)
               self.configuration = load_script(dict["configuration_file_name"],'configuration')
               self.fitness = load_script(dict["fitness_file_name"],'fitness')
        except Exception, e:
            logging.error('Error loading run\'s run_data.txt. Cannot restart '
                          'without this file. {}'.format(str(e)))
            logging.error('Could not load fitness and/or configuration '
                          'scripts. Terminating...')            
            logging.error('Check if configuration script ' + str(dict["configuration_file_name"]) + ' and fitness script ' + str(dict["fitness_file_name"]) + ' are in the specified directories.')
            sys.exit(1)
        
        self.set_state_dictionary(dict)
        
        for trial_no in range(0, self.get_no_of_trials()): ###
            trial = self.get_trial_type_constructor()(trial_no, self.get_name(), self.fitness,  self.configuration, self.controller, self.results_folder_path)
            trial.run_initialize()
            if not trial.load():
                logging.error('Failed loading a trial no.'.format(
                    trial.get_trial_no()))
                sys.exit(1)
            ##print trial.state_dictionary
            self.trials.append(trial)
            
        # Run trials
        for trial in self.trials:
            trial.daemon = True
            trial.start()
        
    def save(self):
        try:
            dict = self.get_state_dictionary()
            with open(self.results_folder_path + '/run_data.txt', 'w') as outfile:
                pickle.dump(dict, outfile)    
        except Exception, e:
            logging.error(str(e))
            return False
                        
    ## creates a snapshot dictionary representing the state of the trials within the run.. basically get snapshots from all the trials.
    ## feel free to add anything extra you thing would be neccesary to generate views of a run
    def snapshot(self):
        snapshot_dict = {"trial_type" : self.get_trial_type(),
                         "run_name" : self.get_name()
                         }
        for trial in self.trials:
            snapshot_dict[tria.get_name()] = trial.snapshot()
        return snapshot_dict
        
    #############
    ## GET/SET ##
    #############
    
    def get_status(self):
        return self.state_dictionary["status"]

    def set_status(self, status):
        self.state_dictionary["status"] = status
    
    def get_wait(self):
        return self.state_dictionary["wait"]
    
    def set_wait(self, wait):
        self.state_dictionary["wait"] = True
        
    def get_run_file(self):
        return self.results_folder_path + '/run_data.txt'
    
    def set_state_dictionary(self, dict):
        self.state_dictionary = dict
        
    def get_state_dictionary(self):
        return self.state_dictionary

    def get_no_of_trials(self):
        return self.state_dictionary["no_of_trials"]
        
    def set_no_of_trials(self, num):
        self.state_dictionary["no_of_trials"] = num    
        
    def set_name(self, name):
        self.state_dictionary["name"] = name
        
    def get_name(self):
        return self.state_dictionary["name"]
        
    def set_trial_type(self, trial_type):
        self.state_dictionary["trial_type"] = trial_type

    def get_trial_type(self):
        return self.state_dictionary["trial_type"]
        
    def get_trial_type_constructor(self):
        return get_trial_constructor(self.get_trial_type())
        
    def set_results_folder_path(self, folder):
        self.results_folder_path = folder