# Copyright (c) 2013 Shotgun Software Inc.
#
# CONFIDENTIAL AND PROPRIETARY
#
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights
# not expressly granted therein are reserved by Shotgun Software Inc.

from tank import Hook
import maya.cmds as cmds
import pymel.core as pm
from PKD_tools import libFile, libShader
import os


class BreakdownSceneOperations(Hook):
    """
    Breakdown operations for Maya.

    This implementation handles detection of maya references and file texture nodes.
    """

    def scan_scene(self):
        """
        The scan scene method is executed once at startup and its purpose is
        to analyze the current scene and return a list of references that are
        to be potentially operated on.

        The return data structure is a list of dictionaries. Each scene reference
        that is returned should be represented by a dictionary with three keys:

        - "node": The name of the 'node' that is to be operated on. Most DCCs have
          a concept of a node, path or some other way to address a particular
          object in the scene.
        - "type": The object type that this is. This is later passed to the
          update method so that it knows how to handle the object.
        - "path": Path on disk to the referenced object.

        Toolkit will scan the list of items, see if any of the objects matches
        any templates and try to determine if there is a more recent version
        available. Any such versions are then displayed in the UI as out of date.
        """

        refs = []

        # first let's look at maya references
        for x in pm.listReferences():
            node_name = x.refNode.longName()

            # get the path and make it platform dependent
            # (maya uses C:/style/paths)
            maya_path = x.path.replace("/", os.path.sep)
            refs.append({"node": node_name, "type": "reference", "path": maya_path})

        # now look at file texture nodes
        for file_node in cmds.ls(l=True, type="file"):
            # ensure this is actually part of this scene and not referenced
            if cmds.referenceQuery(file_node, isNodeReferenced=True):
                # this is embedded in another reference, so don't include it in the breakdown
                continue

            # get path and make it platform dependent (maya uses C:/style/paths)
            path = cmds.getAttr("%s.fileTextureName" % file_node).replace("/", os.path.sep)

            refs.append({"node": file_node, "type": "file", "path": path})

        return refs

    def update(self, items):
        """
        Perform replacements given a number of scene items passed from the app.

        Once a selection has been performed in the main UI and the user clicks
        the update button, this method is called.

        The items parameter is a list of dictionaries on the same form as was
        generated by the scan_scene hook above. The path key now holds
        the that each node should be updated *to* rather than the current path.
        """

        engine = self.parent.engine

        for i in items:
            node = i["node"]
            node_type = i["type"]
            new_path = i["path"]

            if node_type == "reference":

                # Check if it is surfacing task
                if "surface" in new_path:
                    self._check_existing_model_alembic_(new_path, node)

                # maya reference
                engine.log_debug("Maya Reference %s: Updating to version %s" % (node, new_path))
                rn = pm.system.FileReference(node)
                rn.replaceWith(new_path)

                if rn.namespace != ":":
                    # Update the namespace
                    newNameSpace = libFile.get_file_folder_extension(new_path)[0]
                    rn.namespace = newNameSpace

                # Load the shaders into scene
                if "surface" in new_path:
                    self._update_published_shaders(new_path)


            elif node_type == "file":
                # file texture node
                engine.log_debug("File Texture %s: Updating to version %s" % (node, new_path))
                file_name = cmds.getAttr("%s.fileTextureName" % node)
                cmds.setAttr("%s.fileTextureName" % node, new_path, type="string")

    def _check_existing_model_alembic_(self, path,node):
        # Get the model path for the updated shader
        tk = self.parent.tank
        publishField = tk.template_from_path(path).get_fields(path)
        dataFolderTemplate = tk.templates["maya_asset_data_publish"]
        dataFolder = dataFolderTemplate.apply_fields(publishField)

        reload(libShader)
        # Intialise the Shader API
        self.shaderAPI = libShader.MDSshaderAPI()
        self.shaderAPI.dataFolder = dataFolder
        modelUsed = self.shaderAPI.get_model_info()



        # Search for the namespace associated with this model
        self.alembicNamespaces = []
        for transform in pm.ls(type="transform"):
            if transform.hasAttr("Namespace"):
                # check if matches the geo
                if transform.ModelUsed.get():
                    if transform.ModelUsed.get().lower() == modelUsed.lower():
                        self.alembicNamespaces.append(transform.Namespace.get())

        # Does it exists in scene?
        if not len(self.alembicNamespaces):
            # Error Messsage
            raise Exception("No Alembics found associated that matches the model used in the published Surface task.")

        # Get the namespace from the shader
        rn = pm.system.FileReference(node)
        namespace = rn.namespace

        # Get the list of shaders from the old reference node.
        for shader in self.shaderAPI.used_shaders:
            if namespace in shader:
                # Delete the shaders
                self.shaderAPI.safe_delete_shading_network(shader)

        # Delete the displacement node
        pm.delete(pm.ls("%s:*"%namespace,type="VRayDisplacement"))



    def _update_published_shaders(self, path):
        # Reimport the shader and remap

        self.shaderAPI.namespace = "%s:"%self.alembicNamespaces[0]
        self.shaderAPI.import_all_shading_and_connection_info()

        if len(self.alembicNamespaces) > 1:
            for nameSpace in self.alembicNamespaces[1:]:
                self.shaderAPI.namespace = "%s:"%nameSpace
                self.shaderAPI.reapply_all_shaders()