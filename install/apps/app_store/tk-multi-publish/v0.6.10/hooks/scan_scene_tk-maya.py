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

import tank
from tank import Hook
from tank import TankError

class ScanSceneHook(Hook):
    """
    Hook to scan scene for items to publish
    """
    
    def execute(self, **kwargs):
        """
        Main hook entry point
        :returns:       A list of any items that were found to be published.  
                        Each item in the list should be a dictionary containing 
                        the following keys:
                        {
                            type:   String
                                    This should match a scene_item_type defined in
                                    one of the outputs in the configuration and is 
                                    used to determine the outputs that should be 
                                    published for the item
                                    
                            name:   String
                                    Name to use for the item in the UI
                            
                            description:    String
                                            Description of the item to use in the UI
                                            
                            selected:       Bool
                                            Initial selected state of item in the UI.  
                                            Items are selected by default.
                                            
                            required:       Bool
                                            Required state of item in the UI.  If True then
                                            item will not be deselectable.  Items are not
                                            required by default.
                                            
                            other_params:   Dictionary
                                            Optional dictionary that will be passed to the
                                            pre-publish and publish hooks
                        }
        """   
                
        items = []
        
        # get the main scene:
        scene_name = cmds.file(query=True, sn=True)
        if not scene_name:
            raise TankError("Please Save your file before Publishing")
        
        scene_path = os.path.abspath(scene_name)
        name = os.path.basename(scene_path)

        # create the primary item - this will match the primary output 'scene_item_type':            
        items.append({"type": "work_file", "name": name})
        
        # if there is any geometry in the scene (poly meshes or nurbs patches), then
        # add a geometry item to the list:
        if cmds.ls(geometry=True, noIntermediate=True):
            items.append({"type":"geometry", "name":"All Scene Geometry"})


# Added by Chetan Patel
# May 2016 (KittenWitch Project)
# ------------------------------------------------
# Adds rendered image publishing functionality to maya
# Based on the two Two Guys and a Toolkit
# ------------------------------------------------

        # we'll use the engine to get the templates
        engine = tank.platform.current_engine()

        # get the "maya_shot_work" template to grab some info from the current
        # work file. get_fields will pull out the version number for us.
        work_template = engine.tank.templates.get("maya_shot_work")
        work_template_fields = work_template.get_fields(scene_name)
        version = work_template_fields["version"]

        # now grab the render template to match against.
        render_template = engine.tank.templates.get("maya_shot_render_folder")

        # now look for rendered images. note that the cameras returned from
        # listCameras will include full DAG path. You may need to account
        # for this in your, more robust solution, if you want the camera name
        # to be part of the publish path. For my simple test, the cameras
        # are not parented, so there is no hierarchy.

        # iterate over all render layers

        for layer in cmds.ls(type="renderLayer"):

            # apparently maya has 2 names for the default layer. I'm
            # guessing it actually renders out as 'masterLayer'.
            layer = layer.replace("defaultRenderLayer", "masterLayer")

            # these are the fields to populate into the template to match
            # against
            fields = {
                'render_layer': layer,
                'name': layer,
                'version': version,
                }

            # match existing paths against the render template
            paths = engine.tank.abstract_paths_from_template(
                render_template, fields)

            # if there's a match, add an item to the render
            if paths:
                items.append({
                    "type": "maya_rendered_image",
                    "name": layer,
                    # since we already know the path, pass it along for
                    # publish hook to use
                    "other_params": {
                        # just adding first path here. may want to do some
                        # additional validation if there are multiple.
                        'path': paths[0],
                    }
                })

        return items
