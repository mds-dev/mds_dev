# Copyright (c) 2015 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

"""
Hook that loads defines all the available actions, broken down by publish type. 
"""
import sgtk
import os
import pymel.core as pm
import maya.cmds as cmds
import maya.mel as mel
from PKD_tools import libShader


HookBaseClass = sgtk.get_hook_baseclass()

class MayaActions(HookBaseClass):
    
    ##############################################################################################################
    # public interface - to be overridden by deriving classes 
    
    def generate_actions(self, sg_publish_data, actions, ui_area):
        """
        Returns a list of action instances for a particular publish.
        This method is called each time a user clicks a publish somewhere in the UI.
        The data returned from this hook will be used to populate the actions menu for a publish.
    
        The mapping between Publish types and actions are kept in a different place
        (in the configuration) so at the point when this hook is called, the loader app
        has already established *which* actions are appropriate for this object.
        
        The hook should return at least one action for each item passed in via the 
        actions parameter.
        
        This method needs to return detailed data for those actions, in the form of a list
        of dictionaries, each with name, params, caption and description keys.
        
        Because you are operating on a particular publish, you may tailor the output 
        (caption, tooltip etc) to contain custom information suitable for this publish.
        
        The ui_area parameter is a string and indicates where the publish is to be shown. 
        - If it will be shown in the main browsing area, "main" is passed. 
        - If it will be shown in the details area, "details" is passed.
        - If it will be shown in the history area, "history" is passed. 
        
        Please note that it is perfectly possible to create more than one action "instance" for 
        an action! You can for example do scene introspection - if the action passed in 
        is "character_attachment" you may for example scan the scene, figure out all the nodes
        where this object can be attached and return a list of action instances:
        "attach to left hand", "attach to right hand" etc. In this case, when more than 
        one object is returned for an action, use the params key to pass additional 
        data into the run_action hook.
        
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :param actions: List of action strings which have been defined in the app configuration.
        :param ui_area: String denoting the UI Area (see above).
        :returns List of dictionaries, each with keys name, params, caption and description
        """
        app = self.parent
        app.log_debug("Generate actions called for UI element %s. "
                      "Actions: %s. Publish Data: %s" % (ui_area, actions, sg_publish_data))
        
        action_instances = []
        
        if "reference" in actions:
            action_instances.append( {"name": "reference", 
                                      "params": None,
                                      "caption": "Create Reference", 
                                      "description": "This will add the item to the scene as a standard reference."} )

        if "import" in actions:
            action_instances.append( {"name": "import", 
                                      "params": None,
                                      "caption": "Import into Scene", 
                                      "description": "This will import the item into the current scene."} )

        if "texture_node" in actions:
            action_instances.append( {"name": "texture_node",
                                      "params": None, 
                                      "caption": "Create Texture Node", 
                                      "description": "Creates a file texture node for the selected item.."} )
            
        if "udim_texture_node" in actions:
            # Special case handling for Mari UDIM textures as these currently only load into 
            # Maya 2015 in a nice way!
            if self._get_maya_version() >= 2015:
                action_instances.append( {"name": "udim_texture_node",
                                          "params": None, 
                                          "caption": "Create Texture Node", 
                                          "description": "Creates a file texture node for the selected item.."} )    
        return action_instances

    def execute_action(self, name, params, sg_publish_data):
        """
        Execute a given action. The data sent to this be method will
        represent one of the actions enumerated by the generate_actions method.
        
        :param name: Action name string representing one of the items returned by generate_actions.
        :param params: Params data, as specified by generate_actions.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        :returns: No return value expected.
        """
        app = self.parent
        app.log_debug("Execute action called for action %s. "
                      "Parameters: %s. Publish Data: %s" % (name, params, sg_publish_data))
        
        # resolve path
        path = self.get_publish_path(sg_publish_data)
        
        if name == "reference":
            self._create_reference(path, sg_publish_data)

        if name == "import":
            self._do_import(path, sg_publish_data)
        
        if name == "texture_node":
            self._create_texture_node(path, sg_publish_data)
            
        if name == "udim_texture_node":
            self._create_udim_texture_node(path, sg_publish_data)
                        
           
    ##############################################################################################################
    # helper methods which can be subclassed in custom hooks to fine tune the behaviour of things
    
    def _create_reference(self, path, sg_publish_data):
        """
        Create a reference with the same settings Maya would use
        if you used the create settings dialog.
        
        :param path: Path to file.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        """
        if not os.path.exists(path):
            raise Exception("File not found on disk - '%s'" % path)
        
        # # make a name space out of entity name + publish name
        # # e.g. bunny_upperbody
        # namespace = "%s %s" % (sg_publish_data.get("entity").get("name"), sg_publish_data.get("name"))
        # namespace = namespace.replace(" ", "_")

        namespace = ""

        if self._create_namespace_():
            # make a name space out of entity name + publish name
            # e.g. bunny_upperbody
            self.parent.log_info("Shot File:Setting namespace")
            namespace = sg_publish_data.get("code").split(".")[0]
        else:
            self.parent.log_info("Asset File:No Namespace Needed")
            namespace = ":"

        ref = pm.system.createReference(path,
                                      loadReferenceDepth= "all",
                                      mergeNamespacesOnClash=False,
                                      namespace=namespace)

        # Load the shaders into scene
        if any(x in path for x in ["sculpt","surface"]):
            print "*********************************************"
            print "path is = ".format(path)
            self._import_published_shaders(path,ref)
            #Hack to stop reference also being loaded - as file is not empty anymore
            cmds.file(path,removeReference=True)





    def _import_published_shaders(self,path,ref):
        tk = sgtk.sgtk_from_path(path)
        # Get the fields
        template_obj = tk.template_from_path(path)
        fields = template_obj.get_fields(path)
        template_obj.apply_fields(fields)
        # Get the data folder
        dataTemplate = tk.templates["maya_asset_data_publish"]
        published_data_folder = dataTemplate.apply_fields(fields)
        print "******************************"
        print "published_data_folder = ".format(published_data_folder)

        # Init the ShaderAPI
        reload(libShader)
        shaderAPI = libShader.MDSshaderAPI()
        shaderAPI.dataFolder = published_data_folder

        # Get the model info associated with this model
        modelUsed = shaderAPI.get_model_info()

        # Search for the namespace associated with this model
        nameSpaces = []
        for transform in pm.ls(type="transform"):
            if transform.hasAttr("Namespace"):
                # check if matches the geo
                if transform.ModelUsed.get():
                    if transform.ModelUsed.get().lower() == modelUsed.lower():
                        nameSpaces.append(transform.Namespace.get())

        if nameSpaces:
            # Apply the shader to the first namespace
            shaderAPI.namespace = "%s:"%nameSpaces[0]
            shaderAPI.import_all_shading_and_connection_info()

            # Reapply to the all the rest
            if len(nameSpaces) > 1:
                for nameSpace in nameSpaces[1:]:
                    shaderAPI.namespace = "%s:"%nameSpace
                    shaderAPI.reapply_all_shaders()

            shaderAPI.assetNameSpace = ref.namespace
            shaderAPI.add_shader_nameSpace()
            # Add namespaces to the Shaders
        else:
            ref.remove()
            raise Exception("No Alembics found associated that matches the model used in the published Surface task")

    def _create_namespace_(self):
        """Only create a namespace if referencing a asset in to shot scene"""
        scenename =  pm.sceneName()
        self.parent.log_info("SceneName:%s"%scenename)
        # Has the scene been saved
        if scenename:
            # Check to see if is a shot or asset
            tk = sgtk.sgtk_from_path(scenename)
            template_obj = tk.template_from_path(scenename)
            # Return the vale
            return template_obj.get_fields(scenename).has_key("Shot")
        else:
            # Due to fact the scene has not been saved, we use namespace just in case it is shot
            return True

    def _do_import(self, path, sg_publish_data):
        """
        Create a reference with the same settings Maya would use
        if you used the create settings dialog.
        
        :param path: Path to file.
        :param sg_publish_data: Shotgun data dictionary with all the standard publish fields.
        """
        if not os.path.exists(path):
            raise Exception("File not found on disk - '%s'" % path)
                
        # make a name space out of entity name + publish name
        # e.g. bunny_upperbody                
        namespace = "%s %s" % (sg_publish_data.get("entity").get("name"), sg_publish_data.get("name"))
        namespace = namespace.replace(" ", "_")
        
        # perform a more or less standard maya import, putting all nodes brought in into a specific namespace
        cmds.file(path, i=True, renameAll=True, namespace=namespace, loadReferenceDepth="all", preserveReferences=True)
            
    def _create_texture_node(self, path, sg_publish_data):
        """
        Create a file texture node for a texture
        
        :param path:             Path to file.
        :param sg_publish_data:  Shotgun data dictionary with all the standard publish fields.
        :returns:                The newly created file node
        """
        file_node = cmds.shadingNode('file', asTexture=True)
        cmds.setAttr( "%s.fileTextureName" % file_node, path, type="string" )
        return file_node

    def _create_udim_texture_node(self, path, sg_publish_data):
        """
        Create a file texture node for a UDIM (Mari) texture
        
        :param path:             Path to file.
        :param sg_publish_data:  Shotgun data dictionary with all the standard publish fields.
        :returns:                The newly created file node
        """
        # create the normal file node:
        file_node = self._create_texture_node(path, sg_publish_data)
        if file_node:
            # path is a UDIM sequence so set the uv tiling mode to 3 ('UDIM (Mari)')
            cmds.setAttr("%s.uvTilingMode" % file_node, 3)
            # and generate a preview:
            mel.eval("generateUvTilePreview %s" % file_node)
        return file_node
            
    def _get_maya_version(self):
        """
        Determine and return the Maya version as an integer
        
        :returns:    The Maya major version
        """
        if not hasattr(self, "_maya_major_version"):
            self._maya_major_version = 0
            # get the maya version string:
            maya_ver = cmds.about(version=True)
            # handle a couple of different formats: 'Maya XXXX' & 'XXXX':
            if maya_ver.startswith("Maya "):
                maya_ver = maya_ver[5:]
            # strip of any extra stuff including decimals:
            major_version_number_str = maya_ver.split(" ")[0].split(".")[0]
            if major_version_number_str and major_version_number_str.isdigit():
                self._maya_major_version = int(major_version_number_str)
        return self._maya_major_version
        
