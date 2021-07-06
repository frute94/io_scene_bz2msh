import bpy
import re # Reading .material files
from mathutils import Matrix, Vector, Euler, Quaternion
from bpy_extras import image_utils
from math import radians

from . import bz2msh
import os

PRINT_TEXTURE_FINDER_INFO = False
PRINT_LOCAL_MATERIAL_REUSE = False
PRINT_MSH_HEADER = True

NODE_NORMALMAP_STRENGTH = 0.10
NODE_EMISSIVE_STRENGTH = 1.0
NODE_DEFAULT_ROUGHNESS = 0.50

# Emulate mesh render flags
USE_RENDER_FLAGS = True
RENDER_FLAGS_RENAME = True # add __h2cg etc to object name

# Visual placement for material nodes in the blender node editor
NODE_SPACING_X, NODE_SPACING_Y = 600, 300
NODE_HEIGHT = {
	"diffuse": NODE_SPACING_Y,
	"specular": 0,
	"emissive": -NODE_SPACING_Y,
	"normal": -(NODE_SPACING_Y*2)
}

def find_texture(texture_filepath, search_directories, acceptable_extensions, recursive=False):
	acceptable_extensions = list(acceptable_extensions)
	
	file_name, original_extension = os.path.splitext(os.path.basename(texture_filepath))
	original_extension_compare = original_extension.lower()
	is_material_file = bool(original_extension_compare == ".material")
	
	# Exact path match
	if os.path.exists(texture_filepath):
		if PRINT_TEXTURE_FINDER_INFO:
			print("TEXTURE FINDER %r:" % file_name, "original path %r was exact match." % texture_filepath)
		return texture_filepath
	
	if is_material_file:
		# Only look for .material files
		acceptable_extensions = [original_extension_compare]
	else:
		while original_extension_compare in acceptable_extensions:
			# Remove if already present, so we don't look twice
			del acceptable_extensions[acceptable_extensions.index(original_extension_compare)]
		
		# Originally specified extension will be searched for first
		if original_extension_compare in acceptable_extensions:
			acceptable_extensions = [original_extension] + acceptable_extensions
	
	for ext in acceptable_extensions:
		for directory in search_directories:
			for root, folders, files in os.walk(directory):
				path = os.path.join(root, file_name + ext)
				if PRINT_TEXTURE_FINDER_INFO:
					print("TEXTURE FINDER %r:" % file_name, "Checking for", path)
				
				if os.path.exists(path) and os.path.isfile(path):
					if PRINT_TEXTURE_FINDER_INFO:
						print("TEXTURE FOUND FOR %r:" % file_name, "%r success." % path)
					return path
				
				if not recursive:
					break
	
	if PRINT_TEXTURE_FINDER_INFO:
		print("TEXTURE FINDER %r:" % file_name, "Texture not found.")
	
	return file_name + original_extension

def read_material_file(filepath, default_diffuse=None):
	re_section = re.compile(r"(?i)\s*\[([^\]]*)\]")
	re_keyval = re.compile(r"(?i)\s*(\w+)\s*=\s*(.+)")
	
	textures = {"diffuse": default_diffuse, "specular": None, "normal": None, "emissive": None}
	counter = 0
	in_texture = False
	with open(filepath, "r") as f:
		for line in f:
			match = re_section.match(line)
			if match:
				if in_texture:
					break
				
				if match.group(1).lower() == "texture":
					in_texture = True
				
				continue
			
			if in_texture:
				match = re_keyval.match(line)
				if match:
					key = match.group(1).lower()
					value = match.group(2)
					
					if key in textures:
						textures[key] = value
	
	return textures

class Load:
	def __init__(self, operator, context, filepath="", as_collection=False, **opt):
		self.opt = opt
		self.context = context
		
		self.name = os.path.basename(filepath)
		self.filefolder = os.path.dirname(filepath)
		self.ext_list = self.opt["find_textures_ext"].casefold().split()
		self.tex_dir = self.context.preferences.filepaths.texture_directory
		
		self.bpy_objects = []
		bpy_root_objects = []
		
		# Entire .msh file is read into this object first
		msh = bz2msh.MSH(filepath)
		
		collection = self.context.view_layer.active_layer_collection.collection
		if as_collection:
			collection = bpy.data.collections.new(os.path.basename(filepath))
			bpy.context.scene.collection.children.link(collection)
		
		if PRINT_MSH_HEADER:
			print("\nMSH %r" % os.path.basename(filepath))
			for block in msh.blocks:
				print("\nBlock %r MSH Header:" % block.name)
				print("- dummy:", block.msh_header.dummy)
				print("- scale:", block.msh_header.scale)
				print("- indexed:", block.msh_header.indexed)
				print("- moveAnim:", block.msh_header.moveAnim)
				print("- oldPipe:", block.msh_header.oldPipe)
				print("- isSingleGeometry:", block.msh_header.isSingleGeometry)
				print("- skinned:", block.msh_header.skinned, "\n")
		
		# Deselect all objects in blender
		for bpy_obj in context.scene.objects:
			bpy_obj.select_set(False)
		
		if opt["import_mode"] == "GLOBAL":
			for block in msh.blocks:
				bpy_obj = self.create_object(
					block.name,
					self.create_global_mesh(block),
					self.create_matrix(Matrix()),
					None
				)
				
				scale = block.msh_header.scale
				bpy_obj.scale = Vector((scale, scale, scale))
				bpy_root_objects.append(bpy_obj)
		
		elif opt["import_mode"] == "LOCAL":
			# Reuse same-named materials for each local mesh
			self.existing_materials = {} # {str(name of msh material): bpy.types.Material(blender material object)}
			for block in msh.blocks:
				bpy_root_objects.append(self.walk(block.root))
		
		for bpy_obj in bpy_root_objects:
			if self.opt["rotate_for_yz"]:
				bpy_obj.rotation_euler[0] = radians(90)
				bpy_obj.rotation_euler[2] = radians(180)
				bpy_obj.location[1], bpy_obj.location[2] = bpy_obj.location[2], bpy_obj.location[1]
			
			if self.opt["place_at_cursor"]:
				bpy_obj.location += context.scene.cursor.location
		
		for bpy_obj in self.bpy_objects[::-1]:
			collection.objects.link(bpy_obj)
			bpy_obj.select_set(True)
			self.context.view_layer.objects.active = bpy_obj
	
	def walk(self, mesh, bpy_parent=None):
		bpy_obj = self.create_object(
			mesh.name,
			self.create_local_mesh(mesh),
			self.create_matrix(mesh.matrix),
			bpy_parent
		)
		
		if USE_RENDER_FLAGS and bpy_obj.data:
			ignore_hidden = bool(mesh.name.split("_")[0].casefold() in ("flame",))
			append_flags = ""
			
			if mesh.renderflags.value & bz2msh.RS_HIDDEN and not ignore_hidden:
				bpy_obj.hide_render = True
				bpy_obj.display_type = "WIRE"
				append_flags += "h"
			
			if mesh.renderflags.value & bz2msh.RS_COLLIDABLE and not ignore_hidden:
				bpy_obj.hide_render = True
				bpy_obj.display_type = "WIRE"
				append_flags += "c"
			
			if mesh.renderflags.value & bz2msh.DP_DONOTLIGHT:
				# TODO: Diffuse as emissive 1.0 with strength?
				append_flags += "e"
			
			if mesh.renderflags.value & bz2msh.RS_2SIDED:
				# Turn off backface culling if on?
				append_flags += "2"
			
			if mesh.renderflags.value & bz2msh.RS_DST_ONE:
				# Not supported in BZCC I think?
				append_flags += "g"
			
			if RENDER_FLAGS_RENAME and append_flags:
				bpy_obj.name = bpy_obj.name + "__" + append_flags
		
		if not bpy_parent:
			scale = mesh.block.msh_header.scale
			bpy_obj.scale = Vector((scale, scale, scale))
		
		if not bpy_obj.data:
			bpy_obj.empty_display_type = "SINGLE_ARROW"
		
		for msh_sub_mesh in mesh.meshes:
			self.walk(msh_sub_mesh, bpy_obj)
		
		return bpy_obj
	
	def create_normals(self, bpy_mesh, normals):
		try:
			# Note: Setting invalid normals causes a crash when going into edit mode.
			# If possible, at this point we should check for invalid normals that might cause blender to crash.
			bpy_mesh.normals_split_custom_set(normals)
			bpy_mesh.use_auto_smooth = True
		
		except RuntimeError as msg:
			print("MSH importer failed to import normals for %r:" % bpy_mesh.name, msg)
			bpy_mesh.use_auto_smooth = False
	
	def create_uvmap(self, bpy_mesh, uvs):
		bpy_uvmap = bpy_mesh.uv_layers.new().data
		for index, uv in enumerate(uvs):
			bpy_uvmap[index].uv = Vector((uv[0], -uv[1] + 1.0))
	
	def create_vertex_colors(self, bpy_mesh, colors):
		bpy_vcol = bpy_mesh.vertex_colors.new().data
		
		if colors:
			loop_colors = []
			for poly in bpy_mesh.polygons:
				for loop_index in poly.loop_indices:
					loop_colors += [colors[loop_index]]
			
			for index, color in enumerate(loop_colors):
				bpy_vcol[index].color = [value/255 for value in (color.r, color.g, color.b, color.a)]
				
				# BZ2 style: Other values are simply multiplied by the "alpha", unless mesh uses special flag (__g or __e?)
				# alpha = color.a/255
				# bpy_vcol[index].color = [(value/255)*alpha for value in (color.r, color.g, color.b, 1.0)]
	
	def create_matrix(self, msh_matrix):
		return Matrix(list(msh_matrix)).transposed()
	
	def create_object(self, name, data, matrix, bpy_obj_parent=None):
		bpy_obj = bpy.data.objects.new(name=name, object_data=data)
		
		if bpy_obj_parent:
			bpy_obj.parent = bpy_obj_parent
		
		bpy_obj.matrix_local = matrix
		
		self.bpy_objects.append(bpy_obj)
		
		return bpy_obj
	
	def create_global_mesh(self, block):
		if len(block.vertices) <= 0:
			return None
		
		vertices = [tuple(v) for v in block.vertices]
		faces = [tuple(faceobj.verts) for faceobj in block.faces]
		bucky_indices = [int(faceobj.buckyIndex) for faceobj in block.faces]
		
		bpy_mesh = bpy.data.meshes.new(block.name)
		bpy_mesh.from_pydata(vertices, [], faces)
		
		if self.opt["import_mesh_materials"]:
			bpy_materials = []
			for bucky in block.buckydescriptions:
				bpy_materials += [self.create_material(bucky.material, bucky.texture)]
				bpy_mesh.materials.append(bpy_materials[-1])
			
			for index, material_index in enumerate(bucky_indices):
				bpy_mesh.polygons[index].material_index = material_index
		
		if self.opt["import_mesh_uvmap"]:
			if self.opt["data_from_faces"]:
				uvs = []
				for faceobj in block.faces:
					for uv_index in faceobj.uvs:
						uvs += [tuple(block.uvs[uv_index])]
				
				self.create_uvmap(bpy_mesh, uvs)
			
			else:
				self.create_uvmap(bpy_mesh, ((tuple(block.uvs[index])) for index in block.indices))
		
		if self.opt["import_mesh_normals"]:
			if self.opt["data_from_faces"]:
				normals = []
				for faceobj in block.faces:
					for norm_index in faceobj.norms:
						normals += [tuple(block.vertex_normals[norm_index])]
				
				self.create_normals(bpy_mesh, normals)
			
			else:
				self.create_normals(bpy_mesh, [(tuple(block.vertex_normals[index])) for index in block.indices])
		
		if self.opt["import_mesh_vertcolor"]:
			if self.opt["data_from_faces"]:
				colors = []
				if block.vert_colors:
					for faceobj in block.faces:
						for index in faceobj.verts:
							colors += [block.vert_colors[index]]
				
				self.create_vertex_colors(bpy_mesh, colors)
			
			else:
				self.create_vertex_colors(bpy_mesh, [block.vert_colors[index] for index in block.indices])
		
		return bpy_mesh
	
	def create_local_mesh(self, mesh):
		if len(mesh.vertex) <= 0:
			return None
		
		vertices = [(vert.pos.x, vert.pos.y, vert.pos.z) for vert in mesh.vertex]
		
		faces = []
		triangle = []
		for index in mesh.indices:
			triangle += [index]
			if len(triangle) >= 3:
				faces += [triangle]
				triangle = []
		
		if triangle:
			print("Mesh %r has vertex index count indivisible by 3" % mesh.name)
		
		bpy_mesh = bpy.data.meshes.new(mesh.name)
		bpy_mesh.from_pydata(vertices, [], faces)
		
		if self.opt["import_mesh_materials"]:
			bpy_materials = []
			for local_vert_group in mesh.vert_groups:
				lmat, ltex = local_vert_group.material, local_vert_group.texture
				
				if lmat.name in self.existing_materials:
					bpy_materials += [self.existing_materials[lmat.name]]
					if PRINT_LOCAL_MATERIAL_REUSE:
						print("Reusing material:", lmat.name)
				
				else:
					bpy_materials += [self.create_material(lmat, ltex)]
					self.existing_materials[lmat.name] = bpy_materials[-1]
					if PRINT_LOCAL_MATERIAL_REUSE:
						print("New Material %r" % lmat.name)
				
				bpy_mesh.materials.append(bpy_materials[-1])
			
			if len(bpy_materials) > 1:
				print("Warning: Local material imports with more than 1 material per mesh not supported.")
				print("Try importing as global mesh if results look bad.")
		
		if self.opt["import_mesh_uvmap"]:
			uvs = [tuple(mesh.vertex[index].uv) for index in mesh.indices]
			
			self.create_uvmap(bpy_mesh, uvs)
		
		if self.opt["import_mesh_normals"]:
			self.create_normals(bpy_mesh, [tuple(mesh.vertex[index].norm) for index in mesh.indices])
		
		if self.opt["import_mesh_vertcolor"]:
			colors = []
			if mesh.vert_colors:
				for face in faces:
					for index in face:
						colors += [mesh.vert_colors[index]]
			
			self.create_vertex_colors(bpy_mesh, colors)
		
		return bpy_mesh
	
	def create_material_vcolnodes(self, bpy_material, bpy_node_bsdf, bpy_node_texture):
		bpy_node_attribute = bpy_material.node_tree.nodes.new("ShaderNodeAttribute")
		bpy_node_attribute.attribute_name = "Col"
		bpy_node_attribute.attribute_type = "GEOMETRY"
		bpy_node_attribute.location = (-NODE_SPACING_X, NODE_HEIGHT["diffuse"] + NODE_SPACING_Y)
		
		bpy_node_mixrgb = bpy_material.node_tree.nodes.new("ShaderNodeMixRGB")
		bpy_node_mixrgb.inputs[0].default_value = 1.0 # Factor
		bpy_node_mixrgb.blend_type = "MULTIPLY"
		bpy_node_mixrgb.location = (-NODE_SPACING_X/2, NODE_HEIGHT["diffuse"] + NODE_SPACING_Y/2)
		
		bpy_material.node_tree.links.new(
			bpy_node_attribute.outputs["Color"],
			bpy_node_mixrgb.inputs["Color1"]
		)
		
		bpy_material.node_tree.links.new(
			bpy_node_texture.outputs["Color"],
			bpy_node_mixrgb.inputs["Color2"]
		)
		
		bpy_material.node_tree.links.new(
			bpy_node_mixrgb.outputs["Color"],
			bpy_node_bsdf.inputs["Base Color"]
		)
	
	def create_material(self, msh_material=None, msh_texture=None):
		find_in = (self.filefolder, self.tex_dir)
		recursive = self.opt["find_textures"]
		
		material_name = msh_material.name if msh_material else None
		texture_name = msh_texture.name if msh_texture else None
		image_is_material_file = bool(os.path.splitext(material_name)[1].casefold() == ".material" if material_name else None)
		
		bpy_material = bpy.data.materials.new(name=material_name)
		bpy_material.use_nodes = True
		bpy_material.blend_method = "HASHED" # Needed for diffuse textures w/ alpha channel
		bpy_node_bsdf = bpy_material.node_tree.nodes["Principled BSDF"]
		
		bpy_node_bsdf.inputs[0].default_value = tuple(msh_material.diffuse) if msh_material else (1.0, 1.0, 1.0, 1.0) # Diffuse Color
		bpy_node_bsdf.inputs[17].default_value = tuple(msh_material.emissive) if msh_material else (0.0, 0.0, 0.0, 1.0) # Emissive Color
		bpy_node_bsdf.inputs[18].default_value = NODE_EMISSIVE_STRENGTH
		bpy_node_bsdf.inputs[7].default_value = NODE_DEFAULT_ROUGHNESS
		
		if image_is_material_file:
			# .material multiple textures
			material_filepath = find_texture(material_name, find_in, self.ext_list, recursive)
			if os.path.exists(material_filepath):
				texture_names = read_material_file(material_filepath, default_diffuse=texture_name)
				texture_paths = {which: find_texture(name, find_in, self.ext_list, recursive) for (which, name) in texture_names.items() if name}
				
				if PRINT_TEXTURE_FINDER_INFO:
					print(texture_names)
					print(texture_paths)
				
				for which, path in texture_paths.items():
					image = image_utils.load_image(path, place_holder=True, check_existing=True)
					image.colorspace_settings.name = "sRGB"
					
					bpy_node_texture = bpy_material.node_tree.nodes.new("ShaderNodeTexImage")
					bpy_node_texture.label = os.path.basename(path)
					bpy_node_texture.image = image
					bpy_node_texture.location = (-NODE_SPACING_X, NODE_HEIGHT[which])
					
					if which == "diffuse":
						bpy_material.node_tree.links.new(
							bpy_node_bsdf.inputs["Alpha"],
							bpy_node_texture.outputs["Alpha"]
						)
						
						if self.opt["import_mesh_vertcolor"]:
							self.create_material_vcolnodes(bpy_material, bpy_node_bsdf, bpy_node_texture)
						
						else:
							bpy_material.node_tree.links.new(
								bpy_node_texture.outputs["Color"],
								bpy_node_bsdf.inputs["Base Color"]
							)
						
					elif which == "normal":
						image.colorspace_settings.name = "Non-Color"
						
						bpy_node_normalmap = bpy_material.node_tree.nodes.new("ShaderNodeNormalMap")
						bpy_node_normalmap.location = (-NODE_SPACING_X/2, NODE_HEIGHT[which])
						bpy_node_normalmap.inputs[0].default_value = NODE_NORMALMAP_STRENGTH
						
						bpy_material.node_tree.links.new(
							bpy_node_texture.outputs["Color"],
							bpy_node_normalmap.inputs["Color"]
						)
						
						bpy_material.node_tree.links.new(
							bpy_node_normalmap.outputs["Normal"],
							bpy_node_bsdf.inputs["Normal"]
						)
					
					elif which == "specular":
						image.colorspace_settings.name = "Non-Color"
						
						# Alpha channel in specular map is "glossiness".
						bpy_node_invert = bpy_material.node_tree.nodes.new("ShaderNodeInvert")
						bpy_node_invert.location = (-NODE_SPACING_X/2, NODE_HEIGHT[which])
						
						bpy_material.node_tree.links.new(
							bpy_node_texture.outputs["Alpha"],
							bpy_node_invert.inputs["Color"]
						)
						
						bpy_material.node_tree.links.new(
							bpy_node_invert.outputs["Color"],
							bpy_node_bsdf.inputs["Roughness"]
						)
						
						bpy_material.node_tree.links.new(
							bpy_node_invert.outputs["Color"],
							bpy_node_bsdf.inputs["Metallic"]
						)
						
						bpy_material.node_tree.links.new(
							bpy_node_texture.outputs["Color"],
							bpy_node_bsdf.inputs["Specular"]
						)
					
					elif which == "emissive":
						bpy_material.node_tree.links.new(
							bpy_node_bsdf.inputs["Emission"],
							bpy_node_texture.outputs["Color"]
						)
			
		elif texture_name:
			# Simple pre-bzcc mode
			image_filepath = find_texture(texture_name, find_in, self.ext_list, recursive)
			bpy_node_texture = bpy_material.node_tree.nodes.new("ShaderNodeTexImage")
			bpy_node_texture.label = os.path.basename(image_filepath)
			bpy_node_texture.image = image = image_utils.load_image(image_filepath, place_holder=True, check_existing=True)
			bpy_node_texture.location = (-NODE_SPACING_X, 0)
			
			if self.opt["import_mesh_vertcolor"]:
				self.create_material_vcolnodes(bpy_material, bpy_node_bsdf, bpy_node_texture)
			
			else:
				bpy_material.node_tree.links.new(
					bpy_node_texture.outputs["Color"],
					bpy_node_bsdf.inputs["Base Color"]
				)
		
		else:
			# Non-texture material
			bpy_material = bpy.data.materials.new(name=material_name)
			bpy_material.use_nodes = True
			bpy_node_bsdf = bpy_material.node_tree.nodes["Principled BSDF"]
			
			if self.opt["import_mesh_vertcolor"]:
				bpy_node_attribute = bpy_material.node_tree.nodes.new("ShaderNodeAttribute")
				bpy_node_attribute.attribute_name = "Col"
				bpy_node_attribute.attribute_type = "GEOMETRY"
				bpy_node_attribute.location = (-NODE_SPACING_X, NODE_HEIGHT["diffuse"] + NODE_SPACING_Y)
				
				bpy_material.node_tree.links.new(
					bpy_node_attribute.outputs["Color"],
					bpy_node_bsdf.inputs["Base Color"]
				)

		return bpy_material

def load(operator, context, filepath="", **opt):
	multiple_files = opt["multi_select"]
	as_collection = opt["import_collection"] or multiple_files
	
	if not multiple_files:
		Load(operator, context, filepath, as_collection, **opt)
	else:
		for index, filepath in enumerate(multiple_files):
			try:
				print("Importing file %d of %d (%r)" % (index+1, len(multiple_files), filepath))
				Load(operator, context, filepath, as_collection, **opt)
			except Exception as msg:
				print("Exception occurred importing MSH file %r." % filepath)
	
	return {"FINISHED"}
