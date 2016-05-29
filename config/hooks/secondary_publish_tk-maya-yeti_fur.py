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
import shutil
import maya.cmds as cmds
import maya.mel as mel
import pymel.core as pm
import tank
from tank import Hook
from tank import TankError


class PublishHook(Hook):
    """
    Single hook that implements publish functionality for secondary tasks
    """    
    def execute(self, tasks, work_template, comment, thumbnail_path, sg_task, primary_task, primary_publish_path, progress_cb, **kwargs):
        """
        Main hook entry point
        :param tasks:                   List of secondary tasks to be published.  Each task is a 
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
                        
        :param work_template:           template
                                        This is the template defined in the config that
                                        represents the current work file
               
        :param comment:                 String
                                        The comment provided for the publish
                        
        :param thumbnail:               Path string
                                        The default thumbnail provided for the publish
                        
        :param sg_task:                 Dictionary (shotgun entity description)
                                        The shotgun task to use for the publish    
                        
        :param primary_publish_path:    Path string
                                        This is the path of the primary published file as returned
                                        by the primary publish hook
                        
        :param progress_cb:             Function
                                        A progress callback to log progress during pre-publish.  Call:
                                        
                                            progress_cb(percentage, msg)
                                             
                                        to report progress to the UI
                        
        :param primary_task:            The primary task that was published by the primary publish hook.  Passed
                                        in here for reference.  This is a dictionary in the same format as the
                                        secondary tasks above.
        
        :returns:                       A list of any tasks that had problems that need to be reported 
                                        in the UI.  Each item in the list should be a dictionary containing 
                                        the following keys:
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


        # Added by Chetan Patel
        # May 2016 (KittenWitch Project)
        # ------------------------------------------------
        # create and undo chunk to undo the adding of attributes
        # to yeti nodes and ungroup them.
        # ------------------------------------------------
        cmds.undoInfo(state=True, openChunk=True)

        # Added by Chetan Patel
        # May 2016 (KittenWitch Project)
        # ------------------------------------------------
        # If we are publishing fur or a fursim, remove the individual
        # yeti nodes from the task and group them into one.

        yeti_nodes = []
        new_tasks = []
        output = {}

        for task in tasks:
            item = task["item"]
            if item["type"] is "yeti_fur_nodes":
                yeti_nodes.append(item["name"])
                output = (task["output"])
            else:
                new_tasks.append(task)

        tasks = new_tasks
        yeti_group = self.__group_yeti_nodes(yeti_nodes)

        # Added by Chetan Patel
        # May 2016 (KittenWitch Project)
        # ------------------------------------------------
        # Add the group of yeti nodes to the publish tasks

        yeti_item = ({"type": "yeti_fur_nodes", "name": yeti_group})
        new_yeti_task = {"item": yeti_item, "output": output}
        tasks.append(new_yeti_task)

        for task in tasks:
            item = task["item"]
            output = task["output"]
            errors = []
        
            # report progress:
            progress_cb(0, "Publishing", task)

            # Added by Chetan Patel
            # May 2016 (KittenWitch Project)
            # ------------------------------------------------
            # publish yeti_node output
            # ------------------------------------------------
            if item["type"] is "yeti_fur_nodes":
                try:
                    self.__publish_yeti_node(item, output, work_template, primary_publish_path,
                                                         sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                   errors.append("Publish failed - %s" % e)
            else:
                # don't know how to publish this output types!
                errors.append("Don't know how to publish this item!")

            # if there is anything to report then add to result
            if len(errors) > 0:
                # add result:
                results.append({"task":task, "errors":errors})
             
            progress_cb(100)
             
        return results

    def __publish_yeti_node(self, item, output, work_template, primary_publish_path,
                                        sg_task, comment, thumbnail_path, progress_cb):
        """
        Publish an Alembic cache file for the scene and publish it to Shotgun.
        
        :param item:                    The item to publish
        :param output:                  The output definition to publish with
        :param work_template:           The work template for the current scene
        :param primary_publish_path:    The path to the primary published file
        :param sg_task:                 The Shotgun task we are publishing for
        :param comment:                 The publish comment/description
        :param thumbnail_path:          The path to the publish thumbnail
        :param progress_cb:             A callback that can be used to report progress
        """
        # determine the publish info to use
        #
        progress_cb(10, "Determining publish details")


        # get the current scene path and extract fields from it
        # using the work template:
        scene_path = os.path.abspath(cmds.file(query=True, sn=True))
        fields = work_template.get_fields(scene_path)
        publish_version = fields["version"]
        tank_type = output["tank_type"]

        # create the publish path by applying the fields 
        # with the publish template:
        publish_template = output["publish_template"]
        publish_path = publish_template.apply_fields(fields)
        
        # ensure the publish folder exists:
        publish_folder = os.path.dirname(publish_path)
        self.parent.ensure_folder_exists(publish_folder)

        # determine the publish name:
        publish_name = fields.get("Asset") + "_" + fields.get("Step")

        # Find additional info from the scene:
        progress_cb(10, "Analysing scene")

        # Added by Chetan Patel
        # May 2016 (KittenWitch Project)
        # ------------------------------------------------
        #    Add attributes to the yeti nodes.
        # ------------------------------------------------

        self.__add_atributes_to_yeti_nodes()

        # Added by Chetan Patel
        # May 2016 (KittenWitch Project)
        # ------------------------------------------------
        #    select and  export the yeti nodes
        # ------------------------------------------------

        cmds.select(cl=True)
        cmds.select(str(item["name"]))

        progress_cb(30, "Exporting Yeti Nodes")
        try:
            self.parent.log_debug("Executing pymel export command:")
            pm.exportSelected(publish_path,
                              constructionHistory=False,
                              constraints=False,
                              expressions=False,
                              shader=True,
                              type="mayaAscii",
                              force=True)

            # close undo chunk if the export is successful and undo attr additions
            cmds.undoInfo(state=True, closeChunk=True)
            cmds.undo()
        except Exception, e:
            # close undo chunks if the export fails and undo attr additions
            cmds.undoInfo(state=True, closeChunk=True)
            cmds.undo()
            raise TankError("Failed to export Yeti Nodes: %s" % e)

        # register the publish:

        progress_cb(75, "Registering the publish")        
        args = {
            "tk": self.parent.tank,
            "context": self.parent.context,
            "comment": comment,
            "path": publish_path,
            "name": publish_name,
            "version_number": publish_version,
            "thumbnail_path": thumbnail_path,
            "task": sg_task,
            "dependency_paths": [primary_publish_path],
            "published_file_type": tank_type
        }
        tank.util.register_publish(**args)

    # Added by Chetan Patel
    # May 2016 (KittenWitch Project)
    # ------------------------------------------------
    #  helper method to add attributes for the
    #  connected meshes to the yeti nodes
    # ------------------------------------------------
    def __add_atributes_to_yeti_nodes(self):

        #get all the transform of the yeti nodes
        objs = cmds.ls(type='pgYetiMaya', transforms=True)
        objs = objs + cmds.ls(type='pgYetiGroom', transforms=True)
        yetinodes = []
        for i in objs:
            if cmds.objectType(i, isType='pgYetiMaya') or cmds.objectType(i, isType='pgYetiGroom'):
                yetinodes.append(i)

        cmds.select(cl=True)

        long_name = "connectedMeshName"
        nice_name = "Connected Mesh Name"
        long_name_u = "connectedMeshUUID"
        nice_name_u = "Connected Mesh UUID"

        # add the name and uuid of the connected mesh to the yeti node
        for i in yetinodes:
            inputGeometryList = cmds.listConnections(i + ".inputGeometry", s=True, sh=True)
            count = 0
            for geo in inputGeometryList:
                object_uuid = cmds.ls(geo, uuid=True)[0]
                object_name = geo
                transform = cmds.listRelatives(i, parent=True)[0]

                cmds.addAttr(transform, ln=long_name + '' + str(count), nn=nice_name, dt="string")
                cmds.setAttr(transform + '.' + long_name + '' + str(count), object_name, type="string")
                cmds.setAttr(transform + '.' + long_name + '' + str(count), lock=True, type="string")

                cmds.addAttr(transform, ln=long_name_u + '' + str(count), nn=nice_name_u, dt="string")
                cmds.setAttr(transform + '.' + long_name_u + '' + str(count), object_uuid, type="string")
                cmds.setAttr(transform + '.' + long_name_u + '' + str(count), lock=True, type="string")
                count += 1

    # Added by Chetan Patel
    # May 2016 (KittenWitch Project)
    # ------------------------------------------------
    # helper method to group the yeti nodes
    # ------------------------------------------------

    def __group_yeti_nodes(self, yetinodes):
        # define the group from the current shotgun ass
        scene_name = cmds.file(query=True, sn=True)
        tk = tank.tank_from_path(scene_name)
        templ = tk.template_from_path(scene_name)
        fields = templ.get_fields(scene_name)

        group_name = fields['Asset'] + "_yetiFurNodes_v" + str(fields['version']).zfill(3)

        # select the top group yeti nodes to maintain hierarchy
        nodes = []
        for i in yetinodes:
            p = cmds.listRelatives(i, parent=True, fullPath=True)
            nodes.append(p[0].split('|')[1])

        cmds.select(nodes)
        return cmds.group(cmds.ls(sl=True), name=group_name, relative=True)
