# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook which chooses an environment file to use based on the current context.

"""

from tank import Hook

class PickEnvironment(Hook):

    def execute(self, context, **kwargs):
        """
        The default implementation assumes there are three environments, called shot, asset 
        and project, and switches to these based on entity type.
        """
        
        if context.project is None:
            # our context is completely empty! 
            # don't know how to handle this case.
            return None
        
        if context.entity is None:
            # we have a project but not an entity
            return "project"
        
        if context.entity and context.step is None:
            # we have an entity but no step!
            if context.entity["type"] == "Shot":
                return "shot"
            if context.entity["type"] == "Asset":
                return "asset"            
            if context.entity["type"] == "Sequence":
                return "sequence"            

        if context.entity and context.step:
            # we have a step and an entity
            print "======================================================================"
            print "context = {}".format(context)
            print "======================================================================"
            print "context.step = {}".format(context.step)
            print "context.entity = {}".format(context.entity)
            print "======================================================================"
            print "context.entity[type] = {}".format(context.entity["type"])
            print "context.step[name] = {}".format(context.step["name"])
            print "======================================================================"

            if context.entity["type"] == "Asset" and context.step["name"] == "Fur":
                print "entering fur step"
                return "fur_step"
            if context.entity["type"] == "Shot" and context.step["name"] == "Fur":
                print "entering fursim step"
                return "fursim_step"
            if context.entity["type"] == "Shot":
                return "shot_step"
            if context.entity["type"] == "Asset":
                return "asset_step"

        return None
