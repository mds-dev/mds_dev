# Copyright (c) 2013 Shotgun Software Inc.
# 
# CONFIDENTIAL AND PROPRIETARY
# 
# This work is provided "AS IS" and subject to the Shotgun Pipeline Toolkit 
# Source Code License included in this distribution package. See LICENSE.
# By accessing, using, copying or modifying this work you indicate your 
# agreement to the Shotgun Pipeline Toolkit Source Code License. All rights 
# not expressly granted therein are reserved by Shotgun Software Inc.

import tank
from tank import Hook
import shutil
import os

class CopyFile(Hook):
    """
    Hook called when a file needs to be copied
    """
    
    def execute(self, source_path, target_path, **kwargs):
        """
        Main hook entry point
        
        :source_path:   String
                        Source file path to copy
                        
        :target_path:   String
                        Target file path to copy to
        """
        
        # create the folder if it doesn't exist
        dirname = os.path.dirname(target_path)
        if not os.path.isdir(dirname):            
            old_umask = os.umask(0)
            os.makedirs(dirname, 0777)
            os.umask(old_umask)

        # Edited by Chet May 2016
        # Project: KittenWitch
        # =================================================================
        # Change the copy function to something with a bigger buffer size
        # to speed up the snapshotting of larger files.

        # original
        #        shutil.copy(source_path, target_path)

        # new call.
        with open(source_path, "rb") as fin:
            with open(target_path, "wb") as fout:
                shutil.copyfileobj(fin, fout, 1024 * 1024 * 16)