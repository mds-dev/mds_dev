# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import os
import maya.cmds as cmds
import maya.mel as mel

import tank
from tank import Hook
from tank import TankError

class PrePublishHook(Hook):
    """
    Single hook that implements pre-publish functionality
    """
    def execute(self, tasks, work_template, progress_cb, **kwargs):
        """
        Main hook entry point
        :param tasks:           List of tasks to be pre-published.  Each task is be a 
                                dictionary containing the following keys:
                                {   
                                    item:   Dictionary
                                            This is the item returned by the scan hook 
                                            {   
                                                name:           String
                                                description:    String
                                                type:           String
                                                other_params:   Dictionary
                                            }
                                           
                                    output: Dictionary
                                            This is the output as defined in the configuration - the 
                                            primary output will always be named 'primary' 
                                            {
                                                name:             String
                                                publish_template: template
                                                tank_type:        String
                                            }
                                }
                        
        :param work_template:   template
                                This is the template defined in the config that
                                represents the current work file
               
        :param progress_cb:     Function
                                A progress callback to log progress during pre-publish.  Call:
                                
                                    progress_cb(percentage, msg)
                                     
                                to report progress to the UI
                        
        :returns:               A list of any tasks that were found which have problems that
                                need to be reported in the UI.  Each item in the list should
                                be a dictionary containing the following keys:
                                {
                                    task:   Dictionary
                                            This is the task that was passed into the hook and
                                            should not be modified
                                            {
                                                item:...
                                                output:...
                                            }
                                            
                                    errors: List
                                            A list of error messages (strings) to report    
                                }
        """      
        results = []
        
        # validate tasks:

        for task in tasks:
            item = task["item"]
            output = task["output"]
            errors = []
        
            # report progress:
            progress_cb(0, "Validating", task)

            # Added by Chetan Patel
            # May 2016 (KittenWitch Project)
            # ------------------------------------------------
            # added output type yeti node for publishing
            # ------------------------------------------------
            if output["name"] == "yeti_sim_nodes":
                errors.extend(self.__validate_item_for_yeti_node_publish(item))
            else:
                # don't know how to publish this output types!
                errors.append("Don't know how to publish this item!")            

            # if there is anything to report then add to result
            if len(errors) > 0:
                # add result:
                results.append({"task": task, "errors": errors})
                
            progress_cb(100)
            
        return results

    # Added by Chetan Patel
    # May 2016 (KittenWitch Project)
    # ------------------------------------------------
    # validation method for yeti nodes
    # ------------------------------------------------
    def __validate_item_for_yeti_node_publish(self, item):
        """
        Validate that the item is valid to be exported to an alembic cache
        
        :param item:    The item to validate
        :returns:       A list of any errors found during validation that should be reported
                        to the artist
        """
        errors = []

        # check that the yeti plugin is installed
        if not cmds.pluginInfo("pgYetiMaya", q=True, l=1):
            errors.append("Could not find the Yeti Plugin!")

        # check that there is still yeti nodes in the scene:

        objs = cmds.ls(type='pgYetiMaya', transforms=True)

        yeti_nodes = []
        for i in objs:
            if cmds.objectType(i, isType='pgYetiMaya'):
                yeti_nodes.append(i)

        if not yeti_nodes:
            errors.append("The scene does not contain any Yeti nodes!")

        #check that the namespace has been removed
        if ":" in item["name"]:
            errors.append("Found namespace: {}".format(item["name"]))
        # check that the yeti node being published has a cache and the mode correctly set
        if cmds.objectType(item["name"], isType='pgYetiMaya'):
            cachePath = cmds.getAttr("%s.%s" % (item["name"], "cacheFileName"))
            if not cachePath:
                errors.append("No cache file specified for yeti node: {}".format(item["name"]))
            fileMode = cmds.getAttr("%s.%s" % (item["name"], "fileMode"))
            if fileMode == 0:
                errors.append("Cache mode not set on yeti node: {}".format(item["name"]))

        # finally return any errors
        return errors