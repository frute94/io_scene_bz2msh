bl_info = {
	"name": "BZ2 MSH format",
	"author": "FruteSoftware@gmail.com",
	"version": (1, 0, 6),
	"blender": (4, 0, 0),
	"location": "File > Import-Export",
	"description": "Battlezone II MSH Importer",
	"category": "Import-Export"
}

import os
import bpy

from bpy.props import (
	StringProperty,
	BoolProperty,
	FloatProperty,
	EnumProperty,
	CollectionProperty
)

from bpy.types import (
	OperatorFileListElement,
)

from bpy_extras.io_utils import (
	ImportHelper,
	ExportHelper,
	orientation_helper,
	axis_conversion
)

if "bpy" in locals():
	import importlib
	if "msh_blender_importer" in locals(): importlib.reload(msh_blender_importer)
	if "bz2msh" in locals(): importlib.reload(bz2msh)

class ImportMSH(bpy.types.Operator, ImportHelper):
	"""Import BZ2 MSH file"""
	bl_idname = "import_scene.io_scene_bz2msh"
	bl_label = "Import MSH"
	bl_options = {"UNDO", "PRESET"}
	
	directory: StringProperty(subtype="DIR_PATH")
	filename_ext = ".msh"
	filter_glob: StringProperty(default="*.msh", options={"HIDDEN"})
	texture_image_ext_default = ".png .bmp .jpg .jpeg .gif .tga" # ".tif .tiff .jp2 .jc2 .sgi .rgb .bw .cin .dpx .exr .hdr",
	
	files: CollectionProperty(
		name="File Path",
		type=OperatorFileListElement,
	)
	
	import_collection: BoolProperty(
		name="Create Collection",
		description="Import into collection",
		default=False
	)
	
	import_mode: EnumProperty(
		items=(
			("GLOBAL", "Global Mesh", "Import the global mesh"),
			("LOCAL", "Local Meshes", "Import local meshes (with object hierarchy)")
		),
		
		default="LOCAL",
		name="import_mode",
		description="Each import mode has a compromise."
	)
	
	data_from_faces: BoolProperty(
		name="Data from faces",
		description="Import mesh data from loop indices instead of raw block data",
		default=False
	)
		
	import_mesh_normals: BoolProperty(
		name="Normals",
		description="Import mesh normals",
		default=True
	)
	
	import_mesh_vertcolor: BoolProperty(
		name="Vertex Colors",
		description="Import mesh vertex colors",
		default=True
	)

	import_mesh_materials: BoolProperty(
		name="Materials",
		description="Import mesh face materials",
		default=True
	)

	import_mesh_uvmap: BoolProperty(
		name="UV Maps",
		description="Import mesh texture coordinates",
		default=True
	)
	
	find_textures: BoolProperty(
		name="Recursive Image Search",
		description="Search subdirectories for any associated images (Slow for big directories)",
		default=False
	)
	
	find_textures_ext: StringProperty(
		name="Formats",
		description="Additional file extensions to check for (May be very slow when combined with Recursive Image Search)",
		default=texture_image_ext_default
	)
	
	place_at_cursor: BoolProperty(
		name="Place at Cursor",
		description="Imported objects are placed at cursor if enabled, otherwise at center",
		default=False
	)
	
	rotate_for_yz: BoolProperty(
		name="Rotate Root Frames",
		description="Rotate root frames so they match blender's world orientation",
		default=True
	)
	
	def multi_select_files(self):
		multi_select = [os.path.join(self.directory, file_elem.name) for file_elem in self.files]
		multi_select = [path for path in multi_select if os.path.isfile(path)]
		return multi_select if bool(len(multi_select) >= 2) else []

	def draw(self, context):
		layout = self.layout
		multi_select = self.multi_select_files()
		
		layout.prop(self, "import_mode", expand=True)
		if self.import_mode == "GLOBAL":
			layout.prop(self, "data_from_faces")
		
		sub = layout.column()
		if multi_select:
			layout.label(text="%d files will be imported as collections." % len(multi_select))
		
		else:
			sub.prop(self, "import_collection", icon="COLLECTION_NEW")
		layout.separator()
		
		mesh_layout = layout.box()
		sub = mesh_layout.column()
		sub.prop(self, "import_mesh_normals", icon="NORMALS_VERTEX")
		
		sub = mesh_layout.column()
		sub.prop(self, "import_mesh_vertcolor", icon="GROUP_VCOL")
		
		sub = mesh_layout.column()
		sub.prop(self, "import_mesh_materials", icon="MATERIAL_DATA")
		
		sub = mesh_layout.column()
		sub.prop(self, "import_mesh_uvmap", icon="GROUP_UVS")
		layout.separator()
		
		texture_layout = layout.box()
		sub = texture_layout.column()
		sub.prop(self, "find_textures", icon="TEXTURE_DATA")
		sub.enabled = self.import_mesh_materials
		sub = texture_layout.column()
		sub.prop(self, "find_textures_ext")
		sub.enabled = self.import_mesh_materials
		layout.separator()
		
		layout.prop(self, "place_at_cursor", icon="PIVOT_CURSOR")
		layout.prop(self, "rotate_for_yz", icon="ORIENTATION_GLOBAL")
	
	def execute(self, context):
		from . import msh_blender_importer
		keywords = self.as_keywords(ignore=("filter_glob", "directory"))
		keywords["multi_select"] = self.multi_select_files()
		return msh_blender_importer.load(self, context, **keywords)

def menu_func_import(self, context):
	self.layout.operator(ImportMSH.bl_idname, text="BZ2 MSH (.msh)")

classes = (
	ImportMSH,
)

def register():
	for cls in classes:
		bpy.utils.register_class(cls)

	bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

	for cls in classes:
		bpy.utils.unregister_class(cls)

if __name__ == "__main__":
	register()
