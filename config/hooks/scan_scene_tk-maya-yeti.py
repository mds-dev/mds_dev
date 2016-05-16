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


        # Added by Chetan Patel
        # May 2016 (KittenWitch Project)
        # ------------------------------------------------
        # Find all the yeti nodes
        # ------------------------------------------------

        objs = cmds.ls(type='pgYetiMaya', transforms=True)
        objs = objs + cmds.ls(type='pgYetiGroom', transforms=True)
        yeti_nodes = []
        for i in objs:
            if cmds.objectType(i, isType='pgYetiMaya') or cmds.objectType(i, isType='pgYetiGroom'):
                yeti_nodes.append(i)

        # Added by Chetan Patel
        # May 2016 (KittenWitch Project)
        # ------------------------------------------------
        #        select and group the yeti nodes
        # ------------------------------------------------

        yeti_group = self.__group_yeti_nodes(yeti_nodes)

        # Added by Chetan Patel
        # May 2016 (KittenWitch Project)
        # ------------------------------------------------
        # add the group of yeti nodes to the publish tasks
        # ------------------------------------------------

        items.append({"type": "yeti_node", "name": yeti_group})
        return items

    # Added by Chetan Patel
    # May 2016 (KittenWitch Project)
    # ------------------------------------------------
    # helper method to group the yeti nodes
    # ------------------------------------------------
    def __group_yeti_nodes(self, yetinodes):

        #define the group from the current shotgun ass
        scene_name = cmds.file(query=True, sn=True)
        tk = tank.tank_from_path(scene_name)
        templ = tk.template_from_path(scene_name)
        fields = templ.get_fields(scene_name)

        group_name = fields['Asset'] + "_yetiNodes_v" + str(fields['version']).zfill(3)
        print group_name
        #ungroup any previous yeti group exports
        objs = cmds.ls(transforms=True)
        for i in objs:
            if "_yetiNodes_v" in i:
                cmds.select(i)
                cmds.ungroup()

        #select the top group yeti nodes to maintain hierarchy
        nodes = []
        for i in yetinodes:
            p = cmds.listRelatives(i, parent=True, fullPath=True)
            nodes.append(p[0].split('|')[1])

        cmds.select(nodes)
        return cmds.group(cmds.ls(sl=True), name=group_name, relative=True)