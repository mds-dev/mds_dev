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

import tank
from tank import Hook
from tank import TankError

import subprocess

import os.path

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

        # publish all tasks:
        for task in tasks:
            item = task["item"]
            output = task["output"]
            errors = []
        
            # report progress:
            progress_cb(0, "Publishing", task)
        
            # publish alembic_cache output
            if output["name"] == "alembic_cache":
                try:
                    self.__publish_alembic_cache(item, output, work_template, primary_publish_path,
                                                         sg_task, comment, thumbnail_path, progress_cb)
                except Exception, e:
                    errors.append("Publish failed - %s" % e)

# Added by Chetan Patel
# May 2016 (KittenWitch Project)
# ----------------------------------------------------
# A Searching for maya_rendered_images to publish
# Based on the two Two Guys and a Toolkit
# ----------------------------------------------------
            elif item["type"] == "maya_rendered_image":
                try:
                    self.__publish_rendered_images(item, output, work_template, primary_publish_path,
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

    def __publish_alembic_cache(self, item, output, work_template, primary_publish_path, 
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
        publish_name = fields.get("name")
        if not publish_name:
            publish_name = os.path.basename(publish_path)
        
        # Find additional info from the scene:
        #
        progress_cb(10, "Analysing scene")

        # set the alembic args that make the most sense when working with Mari.  These flags
        # will ensure the export of an Alembic file that contains all visible geometry from
        # the current scene together with UV's and face sets for use in Mari.
        alembic_args = ["-renderableOnly",   # only renderable objects (visible and not templated)
                        "-writeFaceSets",    # write shading group set assignments (Maya 2015+)
                        "-uvWrite"           # write uv's (only the current uv set gets written)
                        ]        

        # find the animated frame range to use:
        start_frame, end_frame = self._find_scene_animation_range()
        if start_frame and end_frame:
            alembic_args.append("-fr %d %d" % (start_frame, end_frame))

        # Set the output path: 
        # Note: The AbcExport command expects forward slashes!
        alembic_args.append("-file %s" % publish_path.replace("\\", "/"))

        # build the export command.  Note, use AbcExport -help in Maya for
        # more detailed Alembic export help
        abc_export_cmd = ("AbcExport -j \"%s\"" % " ".join(alembic_args))

        # ...and execute it:
        progress_cb(30, "Exporting Alembic cache")
        try:
            self.parent.log_debug("Executing command: %s" % abc_export_cmd)
            mel.eval(abc_export_cmd)
        except Exception, e:
            raise TankError("Failed to export Alembic Cache: %s" % e)

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
            "published_file_type":tank_type
        }
        tank.util.register_publish(**args)

    def _find_scene_animation_range(self):
        """
        Find the animation range from the current scene.
        """
        # look for any animation in the scene:
        animation_curves = cmds.ls(typ="animCurve")
        
        # if there aren't any animation curves then just return
        # a single frame:
        if not animation_curves:
            return (1, 1)
        
        # something in the scene is animated so return the
        # current timeline.  This could be extended if needed
        # to calculate the frame range of the animated curves.
        start = int(cmds.playbackOptions(q=True, min=True))
        end = int(cmds.playbackOptions(q=True, max=True))        
        
        return (start, end)

# Added by Chetan Patel
# May 2016 (KittenWitch Project)
# ----------------------------------------------------
# A Method for publishing rendered images from maya
# Based on the two Two Guys and a Toolkit
# ----------------------------------------------------

    def __publish_rendered_images(self, item, output, work_template, primary_publish_path,
                                      sg_task, comment, thumbnail_path, progress_cb):


        """
        Publish rendered images and register with Shotgun.

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

        # this is pretty straight forward since the publish file(s) have
        # already been created (rendered). We're really just populating the
        # arguments to send to the sg publish file registration below.
        publish_name = item["name"]

        # we already determined the path in the scan_scene code. so just
        # pull it from that dictionary.
        other_params = item["other_params"]
        render_path = other_params["path"]

        # copy files
        self.__copy_renders(render_path)

        other_params["path"] = other_params["path"].replace("\\work\\", "\\publish\\")

        #change the thumbnail path to one created by nuke from the render layer
        thumbnail_path = self._generate_render_layer_thumbnail(render_path)

        render_path = render_path.replace("\\work\\", "\\publish\\")

        # register the publish:
        progress_cb(75, "Registering the publish")
        args = {
            "tk": self.parent.tank,
            "context": self.parent.context,
            "comment": comment,
            "path": render_path,
            "name": publish_name,
            "version_number": publish_version,
            "thumbnail_path": thumbnail_path,
            "task": sg_task,
            "dependency_paths": [primary_publish_path],
            "published_file_type": tank_type
        }

        tank.util.register_publish(**args)

        # Delete the thumbnail created by nuke
        os.remove(thumbnail_path)

# Added by Chetan Patel
# May 2016 (KittenWitch Project)
# ----------------------------------------------------
# A To generate jpg thumbnails from the exr using
# Nuke
# ----------------------------------------------------
    def _generate_render_layer_thumbnail(self, render_path):

        nukePath = "C:\\apps\\nuke\\9.0v8\\Nuke9.0.exe"
        scene_name = cmds.file(query=True, sn=True)
        dir = os.path.dirname(scene_name)
        pythonScript = dir + "/dummy.py"

        img_dir = os.path.dirname(render_path)
        render_files = os.listdir(img_dir)

        count = 0
        inImage = "Not found"

        for img in render_files:
            if count is int(len(render_files)/2):
                inImage = img
            count +=1

        outImage = os.path.splitext(inImage)[0] + ".jpg"

        frame = os.path.splitext(outImage)[0][-4:]

        try:
            f = open(pythonScript, "w")
            f.write("r = nuke.nodes.Read(file = \"" + img_dir.replace("\\", "/") + "/" + inImage + "\")\n")
            f.write("ref = nuke.createNode(\"Reformat\", \"type scale scale 0.3\")\n")
            f.write("ref.setInput( 0, r )\n")
            f.write("w = nuke.nodes.Write(file = \"" + dir.replace("\\", "/") + "/" + outImage + "\")\n")
            f.write("w.setInput( 0, ref )\n")
            f.write("nuke.execute(\"Write1\", " + frame + " , " + frame + ")")
            f.close()
        except ValueError:
            print "======= Error: {}".format(ValueError)

        subprocess.call("c:\\apps\\nuke\\9.0v8\\nuke9.0.exe -t -i " + pythonScript)
        #remove the pythonscript
        os.remove(pythonScript)

        return dir.replace("\\", "/") + "/" + outImage


# Added by Chetan Patel
# May 2016 (KittenWitch Project)
# --------------------------------------------------------
# A helper method to copy rendered files from maya's work
# area to the publishing area.
# --------------------------------------------------------

    def __copy_renders(self, render_path):

        render_work_dir = os.path.dirname(render_path)
        #swap the "\work\" string with "\publish\"
        render_publish_dir = render_work_dir.replace("\\work\\", "\\publish\\")
        render_files = os.listdir(render_work_dir)

        for file in render_files:
            if not os.path.exists(render_publish_dir):
                old_umask = os.umask(0)
                os.makedirs(render_publish_dir, 0777)
                os.umask(old_umask)

            with open(render_work_dir + "\\" + file, "rb") as fin:
                with open(render_publish_dir + "\\" + file, "wb") as fout:
                    shutil.copyfileobj(fin, fout, 1024 * 1024 * 10)
