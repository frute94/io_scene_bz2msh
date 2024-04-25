"""This module provides a parser and writer for BZ2 .msh files."""
VERSION = 1.12

import json
from ctypes import sizeof, Structure, Array
from ctypes import c_ubyte, c_int32, c_uint16, c_uint32, c_uint16, c_float

MSH_END_OF_OPTIONALS = 0x9709513F
MSH_MATERIAL = 0x9709513E
MSH_TEXTURE = 0x7951FC0B
MSH_CHILD = 0xF74C51EE
MSH_SIBLING = 0xB8990880
MSH_END = 0xA93EB864
MSH_EOF = 0xE3BB47F1

# From "renderflags.txt"
DP_WAIT = 0x1
RS_NOVTXCHECK = 0x2
DP_DONOTCLIP = 0x4
DP_DONOTUPDATEEXTENTS = 0x8
DP_DONOTLIGHT = 0x10 # __e
RS_DRAWTEXT = 0x20
RS_NOALPHA = 0x40
RS_RESERVED1 = 0x80
RS_COLLIDABLE = 0x100 # __c
RS_2SIDED = 0x200 # __2
RS_HIDDEN = 0x400 # __h
RS_NOFOG = 0x800
RS_BLACKFOG = 0x1000
RS_NOSORT = 0x2000
RS_TEXMIRROR = 0x4000
RS_TEXCLAMP = 0x8000
RS_SRC_ZERO = 0x10000
RS_SRC_ONE = 0x20000
RS_SRC_SRCCOLOR = 0x30000
RS_SRC_INVSRCCOLOR = 0x40000
RS_SRC_SRCALPHA = 0x50000
RS_SRC_INVSRCALPHA = 0x60000
RS_SRC_DSTALPHA = 0x70000
RS_SRC_INVDSTALPHA = 0x80000
RS_SRC_DSTCOLOR = 0x90000
RS_SRC_INVDSTCOLOR = 0xa0000
RS_SRC_SRCALPHASAT = 0xb0000
RS_DST_ZERO = 0x100000
RS_DST_ONE = 0x200000 # __g (doesn't seem to work in BZCC)
RS_DST_SRCCOLOR = 0x300000
RS_DST_INVSRCCOLOR = 0x400000
RS_DST_SRCALPHA = 0x500000
RS_DST_INVSRCALPHA = 0x600000
RS_DST_DSTALPHA = 0x700000
RS_DST_INVDSTALPHA = 0x800000
RS_DST_DSTCOLOR = 0x900000
RS_DST_INVDSTCOLOR = 0xa00000
RS_DST_SRCALPHASAT = 0xb00000
RS_RESERVED2 = 0x1000000
RS_RESERVED3 = 0x2000000
RS_RESERVED4 = 0x4000000
RS_RESERVED5 = 0x8000000
RS_TEX_DECAL = 0x10000000
RS_TEX_MODULATE = 0x20000000
RS_TEX_DECALALPHA = 0x30000000
RS_TEX_MODULATEALPHA = 0x40000000
RS_TEX_DECALMASK = 0x50000000
RS_TEX_MODULATEMASK = 0x60000000
RS_TEX_ADD = 0x80000000
DP_MASK = 0x1d
RS_TEXBORDER = 0xc000
RS_NOZWRITE = 0x80000000
RS_SRC_MASK = 0xf0000
RS_DST_MASK = 0xf00000
RS_TEX_MASK = 0xf0000000
RS_BLEND_MASK = 0xf0ff0000
RS_BLEND_DEF = 0x40650000
RS_BLEND_GLOW = 0x40250000
RS_SRC_NONE = 0x0
RS_DST_NONE = 0x0
RS_BLEND_STENCIL_INC = 0x40000000
RS_BLEND_STENCIL_DEC = 0x40100000
RS_BLEND_STENCIL_USE = 0x40010000
RS_BLEND_NODRAW = 0x40210000

class ZeroLengthName(Exception): pass
class UnknownBlock(Exception): pass
class InvalidFormat(Exception): pass

def read_optional_blocks(f):
	block_type_check = c_uint32()
	
	material = None
	f.readinto(block_type_check)
	if block_type_check.value == MSH_MATERIAL:
		material = Material(f)
	else:
		f.seek(f.tell() - sizeof(c_uint32))
	
	texture = None
	f.readinto(block_type_check)
	if block_type_check.value == MSH_TEXTURE:
		texture = Texture(f)
	else:
		f.seek(f.tell() - sizeof(c_uint32))
	
	had_end_marker = False
	f.readinto(block_type_check)
	if block_type_check.value == MSH_END_OF_OPTIONALS:
		had_end_marker = True
	else:
		f.seek(f.tell() - sizeof(c_uint32))
	
	return material, texture, had_end_marker

# This class provides a function that returns a recursive JSON represenation of its data.
class StructureJSON(Structure):
	def json(self):
		json_handled_types = (int, str, float, list, tuple, bool)
		j = {}
		
		for field_name, field_type in self._fields_:
			field_value = getattr(self, field_name)
			
			if issubclass(field_type, __class__):
				# The field is an object of a class that inherits from this class
				field_value = field_value.json()
			
			elif type(field_value) in json_handled_types:
				pass # Primitives handled by python's JSON serializer
			
			elif type(field_value) in (bytes, bytearray):
				field_value = field_value.decode("ascii", "ignore")
			
			else:
				try:
					# Iterable (e.g. float or index array)
					field_value = [value for value in field_value]
				except TypeError:
					field_value = str(field_value)
			
			j[field_name] = field_value
		
		return j

class UVPair(StructureJSON):
	_fields_ = [
		("u", c_float),
		("v", c_float)
	]
	
	def __iter__(self):
		yield self.u
		yield self.v

class Vector(StructureJSON):
	_fields_ = [
		("x", c_float),
		("y", c_float),
		("z", c_float)
	]
	
	def __iter__(self):
		yield self.x
		yield self.y
		yield self.z

class Vertex(StructureJSON):
	_fields_ = [
		("pos", Vector),
		("norm", Vector),
		("uv", UVPair)
	]

class ColorValue(StructureJSON):
	_fields_ = [
		("r", c_float),
		("g", c_float),
		("b", c_float),
		("a", c_float)
	]
	
	def __iter__(self):
		yield self.r
		yield self.g
		yield self.b
		yield self.a

class Color(StructureJSON):
	_fields_ = [
		("b", c_ubyte),
		("g", c_ubyte),
		("r", c_ubyte),
		("a", c_ubyte)
	]
	
	def __iter__(self):
		yield self.b
		yield self.g
		yield self.r
		yield self.a

class Matrix(StructureJSON):
	_fields_ = [
		("right", c_float * 4),
		("up", c_float * 4),
		("front", c_float * 4),
		("posit", c_float * 4)
	]
	
	def __iter__(self):
		yield [f for f in self.right]
		yield [f for f in self.up]
		yield [f for f in self.front]
		yield [f for f in self.posit]

class Quaternion(StructureJSON):
	_fields_ = [
		("s", c_float),
		("x", c_float),
		("y", c_float),
		("z", c_float)
	]
	
	def __iter__(self):
		yield s
		yield x
		yield y
		yield z

class AnimKey(StructureJSON):
	_fields_ = [
		("frame", c_float),
		("type", c_uint32),
		("quat", Quaternion),
		("vect", Vector)
	]

class BlockHeader(StructureJSON):
	_fields_ = [
		("fileType", c_ubyte * 4),
		("verID", c_uint32),
		("blockCount", c_uint32),
		("notUsed", c_ubyte * 32)
	]

class BlockInfo(StructureJSON):
	_fields_ = [
		("key", c_uint32),
		("size", c_uint32)
	]

class Sphere(StructureJSON):
	_fields_ = [
		("radius", c_float),
		("matrix", Matrix),
		("Width", c_float),
		("Height", c_float),
		("Breadth", c_float)
	]

class MSH_Header(StructureJSON):
	_fields_ = [
		("dummy", c_float),
		("scale", c_float),
		("indexed", c_uint32),
		("moveAnim", c_uint32),
		("oldPipe", c_uint32),
		("isSingleGeometry", c_uint32),
		("skinned", c_uint32)
	]

class FaceObj(StructureJSON):
	_fields_ = [
		("buckyIndex", c_uint16),
		("verts", c_uint16 * 3),
		("norms", c_uint16 * 3),
		("uvs", c_uint16 * 3)
	]

class VertIndex(StructureJSON):
	_fields_ = [
		("weight", c_float),
		("index", c_uint16),
	]

class VertIndexContainer:
	def __init__(self, count, array):
		self.count = count
		self.array = array
	
	def json(self):
		return {
			"count": self.count,
			"array": [item.json() for item in self.array],
		}

class Plane(StructureJSON):
	_fields_ = [
		("d", c_float),
		("x", c_float),
		("y", c_float),
		("z", c_float)
	]
	
	def __iter__(self):
		yield d
		yield x
		yield y
		yield z

class BuckyDesc:
	def __init__(self, f=None):
		self.flags = c_uint32()
		self.vert_count = c_uint32()
		self.index_count = c_uint32()
		
		self.material = None
		self.texture = None
		self.end_marker = False
		
		if f:
			self.read(f)
	
	def read(self, f):
		f.readinto(self.flags)
		f.readinto(self.index_count)
		f.readinto(self.vert_count)
		self.material, self.texture, self.end_marker = read_optional_blocks(f)
	
	def json(self):
		j = {
			"flags": self.flags.value,
			"indexCount": self.vert_count.value,
			"vertCount": self.index_count.value
		}
		
		if self.material:
			j["matBlock"] = self.material.json()
		
		if self.texture:
			j["matTexture"] = self.texture.json()
		
		return j

class VertGroup:
	def __init__(self, f=None):
		self.state_index = c_uint32()
		self.vert_count = c_uint32()
		self.index_count = c_uint32()
		self.plane_index = c_uint32()
		
		self.material = None
		self.texture = None
		self.end_marker = False
		
		if f:
			self.read(f)
	
	def read(self, f):
		f.readinto(self.state_index)
		f.readinto(self.vert_count)
		f.readinto(self.index_count)
		f.readinto(self.plane_index)
		self.material, self.texture, self.end_marker = read_optional_blocks(f)
	
	def json(self):
		j = {
			"stateIndex": self.state_index.value,
			"vertCount": self.vert_count.value,
			"indexCount": self.index_count.value,
			"planeIndex": self.plane_index.value
		}
		
		if self.material:
			j["matBlock"] = self.material.json()
		
		if self.texture:
			j["matTexture"] = self.texture.json()
		
		return j

class Material:
	def __init__(self, f=None):
		# Default material names are generated with a CRC function
		# from diffuse, specular, etc inputs into an unsigned 32 bit integer,
		# which is then turned into a hex string appended to "mat".
		self.name = ""
		self.diffuse = ColorValue()
		self.specular = ColorValue()
		self.specular_power = c_float()
		self.emissive = ColorValue()
		self.ambient = ColorValue()
		
		if f:
			self.read(f)
	
	def read(self, f):
		name_length = c_uint16()
		f.readinto(name_length)
		self.name = f.read(name_length.value)[0:-1].decode("ascii", "ignore")
		f.readinto(self.diffuse)
		f.readinto(self.specular)
		f.readinto(self.specular_power)
		f.readinto(self.emissive)
		f.readinto(self.ambient)
	
	def json(self):
		return {
			"name": {
				"string": self.name,
				"length": len(self.name)+1,
			},
		
			"diffuse": self.diffuse.json(),
			"specular": self.specular.json(),
			"specularPower": self.specular_power.value,
			"emissive": self.emissive.json(),
			"ambient": self.ambient.json()
		}

class Texture:
	def __init__(self, f=None):
		self.name = ""
		self.texture_type = c_uint32()
		self.mipmaps = c_uint32()
		
		if f:
			self.read(f)
	
	def read(self, f):
		name_length = c_uint16()
		f.readinto(name_length)
		self.name = f.read(name_length.value)[0:-1].decode("ascii", "ignore")
		f.readinto(self.texture_type)
		f.readinto(self.mipmaps)
	
	def json(self):
		return {
			"name": {
				"string": self.name,
				"length": len(self.name)+1,
			},
			
			"mipMapCount": self.mipmaps.value,
			"type": self.texture_type.value
		}

class Anim:
	def __init__(self, f=None):
		self.index = c_uint32()
		self.max_frame = c_float()
		self.states = []
		
		if f:
			self.read(f)
	
	def read(self, f):
		f.readinto(self.index)
		f.readinto(self.max_frame)
		
		count = c_uint32()
		f.readinto(count)
		self.states = (AnimKey * count.value)()
		f.readinto(self.states)
	
	def json(self):
		return {
			"index": self.index.value,
			"maxFrame": self.max_frame.value,
			"keys": [state.json() for state in self.states]
		}

class AnimList:
	def __init__(self, f=None):
		self.name = ""
		self.anim_type = c_uint32()
		self.max_frame = c_float()
		self.end_frame = c_float()
		
		self.states = []
		self.animations = []
		
		if f:
			self.read(f)
	
	def read(self, f):
		count = c_uint32()
		name_length = c_uint16()
		f.readinto(name_length)
		self.name = f.read(name_length.value)[0:-1].decode("ascii", "ignore")
		
		f.readinto(self.anim_type)
		f.readinto(self.max_frame)
		f.readinto(self.end_frame)
		
		f.readinto(count)
		self.states = (AnimKey * count.value)()
		f.readinto(self.states)
		
		f.readinto(count)
		self.animations = []
		for animation_index in range(count.value):
			self.animations += [Anim(f)]
	
	def json(self):
		return {
			"name": {
				"string": self.name,
				"length": len(self.name)+1,
			},
			
			"type": self.anim_type.value,
			"maxFrame": self.max_frame.value,
			"endFrame": self.end_frame.value,
			
			"animations": [animation.json() for animation in self.animations],
			"states": [animkey.json() for animkey in self.states]
		}

class Mesh:
	def __init__(self, f, block, level=0):
		self.block = block
		
		self.name = ""
		self.state_index = c_uint32()
		self.is_single_geom = c_int32()
		self.renderflags = c_uint32()
		self.matrix = Matrix()
		
		self.vert_colors = (Color * 0)()
		self.planes = (Plane * 0)()
		self.vertex = (Vertex * 0)()
		self.vert_groups = []
		self.indices = (c_uint16 * 0)()
		
		self.child = None
		self.sibling = None
		
		# Used to hierarchize like an XSI
		self.meshes = []
		self.level = level
		
		if f:
			self.read(f)
	
	def read(self, f):
		count = c_uint32()
		name_length = c_uint16()
		
		f.readinto(name_length)
		self.name = f.read(name_length.value)[0:-1].decode("ascii", "ignore")
		
		if len(self.name) <= 0:
			raise ZeroLengthName()
		
		f.readinto(self.state_index)
		f.readinto(self.is_single_geom)
		f.readinto(self.renderflags)
		f.readinto(self.matrix)
		
		f.readinto(count)
		self.vert_colors = (Color * count.value)()
		f.readinto(self.vert_colors)
		
		f.readinto(count)
		self.planes = (Plane * count.value)()
		f.readinto(self.planes)
		
		f.readinto(count)
		self.vertex = (Vertex * count.value)()
		f.readinto(self.vertex)
		
		f.readinto(count)
		self.vert_groups = []
		for i in range(count.value):
			self.vert_groups += [VertGroup(f)]
		
		f.readinto(count)
		self.indices = (c_uint16 * count.value)()
		f.readinto(self.indices)
	
	def walk(self, indentation_level=1):
		for mesh in self.meshes:
			yield mesh, indentation_level
			yield from mesh.walk(indentation_level+1)
	
	def json(self):
		j = {
			"name": {
				"string": self.name,
				"length": len(self.name)+1
			},
			
			"isSingleGeometry": self.is_single_geom.value,
			"renderFlags": self.renderflags.value,
			"stateIndex": self.state_index.value,
			"objectMatrix": self.matrix.json(),
			
			"localColors": [color.json() for color in self.vert_colors],
			"localGroups": [group.json() for group in self.vert_groups],
			"localIndices": [index for index in self.indices],
			"localPlanes": [plane.json() for plane in self.planes],
			"localVertex": [vertex.json() for vertex in self.vertex]
		}
		
		if self.child:
			j["child"] = self.child.json()
		
		if self.sibling:
			j["siblings"] = [self.sibling.json()]
		
		return j

class Block:
	def __init__(self, f, msh):
		self.msh = msh
		
		self.block_info = BlockInfo()
		self.sphere = Sphere()
		self.msh_header = MSH_Header()
		self.name = ""
		
		self.vertices = (Vector * 0)()
		self.vertex_normals = (Vector * 0)()
		self.uvs = (UVPair * 0)()
		self.vert_colors = (Color * 0)()
		self.faces = (FaceObj * 0)()
		self.buckydescriptions = []
		self.vert_to_state = []
		self.vert_groups = []
		self.indices = (c_uint16 * 0)()
		self.planes = (Plane * 0)()
		self.state_matrices = (Matrix * 0)()
		self.states = (AnimKey * 0)()
		self.anim_list = []
		self.root = None
		
		if f:
			self.read(f)
	
	def read(self, f):
		f.readinto(self.block_info)
		
		count = c_uint32()
		block_type = c_uint32()
		name_length = c_uint16()
		f.readinto(name_length)
		self.name = f.read(name_length.value)[0:-1].decode("ascii", "ignore")
		f.readinto(self.sphere)
		f.readinto(self.msh_header)
		
		f.readinto(count)
		self.vertices = (Vector * count.value)()
		f.readinto(self.vertices)
		
		f.readinto(count)
		self.vertex_normals = (Vector * count.value)()
		f.readinto(self.vertex_normals)
		
		f.readinto(count)
		self.uvs = (UVPair * count.value)()
		f.readinto(self.uvs)
		
		f.readinto(count)
		self.vert_colors = (Color * count.value)()
		f.readinto(self.vert_colors)
		
		f.readinto(count)
		self.faces = (FaceObj * count.value)()
		f.readinto(self.faces)
		
		f.readinto(count)
		for index in range(count.value):
			self.buckydescriptions += [BuckyDesc(f)]
		
		f.readinto(count)
		self.vert_to_state = []
		array_count = c_uint32()
		for index in range(count.value):
			f.readinto(array_count)
			array = []
			for count_index in range(array_count.value):
				# f.readinto() for VertIndex causes 8 byte read.
				weight = c_float()
				vertex_index = c_uint16()
				f.readinto(weight)
				f.readinto(vertex_index)
				array += [VertIndex(weight, vertex_index)]
			
			self.vert_to_state += [VertIndexContainer(array_count.value, array)]
		
		f.readinto(count)
		self.vert_groups = []
		for i in range(count.value):
			self.vert_groups += [VertGroup(f)]
		
		f.readinto(count)
		self.indices = (c_uint16 * count.value)()
		f.readinto(self.indices)
		
		f.readinto(count)
		self.planes = (Plane * count.value)()
		f.readinto(self.planes)
		
		f.readinto(count)
		self.state_matrices = (Matrix * count.value)()
		f.readinto(self.state_matrices)
		
		f.readinto(count)
		self.states = (AnimKey * count.value)()
		f.readinto(self.states)
		
		f.readinto(count)
		self.animation_list = []
		for animlist_index in range(count.value):
			self.animation_list += [AnimList(f)]
		
		self.root = Mesh(f, self, 0)
		self.meshes = [self.root]
		
		in_mesh = 1
		indentation_level = 0 # 0 is root level
		mesh_at = [self.root]
		
		while in_mesh > 0:
			f.readinto(block_type)
			if block_type.value == MSH_CHILD:
				this_mesh = Mesh(f, self, indentation_level + 1)
				mesh_at[indentation_level].child = this_mesh
				mesh_at[indentation_level].meshes += [this_mesh]
				
				indentation_level += 1
				in_mesh += 1
				
				if len(mesh_at) < indentation_level+1:
					mesh_at += [this_mesh]
				else:
					mesh_at[indentation_level] = this_mesh
			
			elif block_type.value == MSH_SIBLING:
				this_mesh = Mesh(f, self, indentation_level)
				mesh_at[indentation_level].sibling = this_mesh
				mesh_at[indentation_level-1].meshes += [this_mesh]
				mesh_at[indentation_level] = this_mesh
				
				in_mesh += 1
			
			elif block_type.value == MSH_END:
				in_mesh -= 1
				
				while in_mesh < indentation_level:
					indentation_level -= 1
			
			else:
				raise UnknownBlock("Unhandled Mesh Block %s - Note that oldpoop is not supported." % hex(block_type.value))
		
		f.readinto(block_type)
		
		if block_type.value != MSH_EOF:
			raise InvalidFormat("Unexpected EOF")
	
	def walk(self):
		if self.root:
			yield self.root, 0 # 0 indentation level
			yield from self.root.walk()
	
	def json(self):
		j = {
			"name": {
				"string": self.name,
				"length": len(self.name)+1
			},
			
			"bigSphere": self.sphere.json(),
			"blockInfo": self.block_info.json(),
			
			"vertices": [vertex.json() for vertex in self.vertices],
			"normals": [nomral.json() for nomral in self.vertex_normals],
			"uvs": [uv.json() for uv in self.uvs],
			"colors": [color.json() for color in self.vert_colors],
			"faces": [face.json() for face in self.faces],
			"buckys": [bucky.json() for bucky in self.buckydescriptions],
			"vertToState": [vts.json() for vts in self.vert_to_state],
			"groups": [vg.json() for vg in self.vert_groups],
			"indices": [index for index in self.indices],
			"planes": [plane.json() for plane in self.planes],
			"stateMats": [state_mat.json() for state_mat in self.state_matrices],
			"States": [state.json() for state in self.states],
			"animList": [al.json() for al in self.animation_list],
			
			"mesh": self.root.json()
		}
		
		j.update(self.msh_header.json())
		
		return j

class MSH:
	def __init__(self, file_path):
		self.block_header = BlockHeader()
		self.blocks = []
		
		with open(file_path, "rb") as f:
			self.read(f)
	
	def read(self, f):
		"""Read from MSH open in binary read mode."""
		f.readinto(self.block_header)
		
		for block_index in range(self.block_header.blockCount):
			self.blocks += [Block(f, self)]
	
	def write(self, f):
		"""Write MSH to file open in binary write mode, write to a file path or writable object."""
		DISABLE_END_OF_OPTIONALS = True # Prevent older .msh parsers from crashing (e.g. OMDL1 viewer)
		
		locally_opened = False
		if not hasattr(f, "write"):
			f = open(f, "wb")
			locally_opened = True
		
		def write_name(f, name):
			written_name = name.encode() + b"\0"
			f.write(c_uint16(len(written_name)))
			f.write(written_name)
		
		def write_optionals(f, optionals_container):
			if optionals_container.material:
				f.write(c_uint32(MSH_MATERIAL))
				write_name(f, optionals_container.material.name)
				f.write(optionals_container.material.diffuse)
				f.write(optionals_container.material.specular)
				f.write(optionals_container.material.specular_power)
				f.write(optionals_container.material.emissive)
				f.write(optionals_container.material.ambient)
			
			if optionals_container.texture:
				f.write(c_uint32(MSH_TEXTURE))
				write_name(f, optionals_container.texture.name)
				f.write(optionals_container.texture.texture_type)
				f.write(optionals_container.texture.mipmaps)
			
			if optionals_container.end_marker and not DISABLE_END_OF_OPTIONALS:
				f.write(c_uint32(MSH_END_OF_OPTIONALS))
		
		def write_vert_group(f, vert_group):
			f.write(vert_group.state_index)
			f.write(vert_group.vert_count)
			f.write(vert_group.index_count)
			f.write(vert_group.plane_index)
			write_optionals(f, vert_group)
		
		def write_mesh(f, mesh):
			write_name(f, mesh.name)
			f.write(mesh.state_index)
			f.write(mesh.is_single_geom)
			f.write(mesh.renderflags)
			f.write(mesh.matrix)
			f.write(c_uint32(len(mesh.vert_colors)))
			f.write(mesh.vert_colors)
			f.write(c_uint32(len(mesh.planes)))
			f.write(mesh.planes)
			f.write(c_uint32(len(mesh.vertex)))
			f.write(mesh.vertex)
			
			f.write(c_uint32(len(mesh.vert_groups)))
			for vert_group in mesh.vert_groups:
				write_vert_group(f, vert_group)
			
			f.write(c_uint32(len(mesh.indices)))
			f.write(mesh.indices)
			
			if mesh.child:
				f.write(c_uint32(MSH_CHILD))
				write_mesh(f, mesh.child)
			
			f.write(c_uint32(MSH_END))
			
			if mesh.sibling:
				f.write(c_uint32(MSH_SIBLING))
				write_mesh(f, mesh.sibling)
		
		self.block_header.blockCount = len(self.blocks)
		f.write(self.block_header)
		for block in self.blocks:
			f.write(block.block_info)
			write_name(f, block.name)
			f.write(block.sphere)
			f.write(block.msh_header)
			
			f.write(c_uint32(len(block.vertices)))
			f.write(block.vertices)
			f.write(c_uint32(len(block.vertex_normals)))
			f.write(block.vertex_normals)
			f.write(c_uint32(len(block.uvs)))
			f.write(block.uvs)
			f.write(c_uint32(len(block.vert_colors)))
			f.write(block.vert_colors)
			f.write(c_uint32(len(block.faces)))
			f.write(block.faces)
			
			f.write(c_uint32(len(block.buckydescriptions)))
			for bucky in block.buckydescriptions:
				f.write(bucky.flags)
				f.write(bucky.index_count)
				f.write(bucky.vert_count)
				write_optionals(f, bucky)
			
			f.write(c_uint32(len(block.vert_to_state)))
			for vts_container in block.vert_to_state:
				f.write(c_uint32(vts_container.count))
				for vts in vts_container.array:
					f.write(c_float(vts.weight))
					f.write(c_uint16(vts.index))
			
			f.write(c_uint32(len(block.vert_groups)))
			for vert_group in block.vert_groups:
				write_vert_group(f, vert_group)
			
			f.write(c_uint32(len(block.indices)))
			f.write(block.indices)
			f.write(c_uint32(len(block.planes)))
			f.write(block.planes)
			f.write(c_uint32(len(block.state_matrices)))
			f.write(block.state_matrices)
			f.write(c_uint32(len(block.states)))
			f.write(block.states)
			
			f.write(c_uint32(len(block.animation_list)))
			for al in block.animation_list:
				write_name(f, al.name)
				f.write(al.anim_type)
				f.write(al.max_frame)
				f.write(al.end_frame)
				f.write(c_uint32(len(al.states)))
				f.write(al.states)
				f.write(c_uint32(len(al.animations)))
				for a in al.animations:
					f.write(a.index)
					f.write(a.max_frame)
					f.write(c_uint32(len(a.states)))
					f.write(a.states)
			
			if block.root:
				write_mesh(f, block.root)
			
			f.write(c_uint32(MSH_EOF))
		
		if locally_opened:
			f.close()
	
	def walk(self):
		for block in self.blocks:
			yield from block.walk()
	
	def to_json(self, file_path, indent=None):
		with open(file_path, "w") as f:
			j = {
				"verID": self.block_header.verID,
				"blockCount": self.block_header.blockCount,
				"fileType": bytearray(self.block_header.fileType).decode("ascii", "ignore"),
				"notUsed": " ".join(["%02X" % x for x in self.block_header.notUsed])
			}
			
			j["meshRoot"] = [block.json() for block in self.blocks]
			
			# If you want improved performance in writing & parsing JSON data, do not sort keys or indent.
			f.write(json.dumps(j, sort_keys=bool(indent), indent=indent))

# Dump .msh data into humanly readable JSON file
if __name__ == "__main__":
	import sys, os
	for msh_file in sys.argv[1::]:
		msh = MSH(msh_file)
		json_file = os.path.join(os.path.dirname(msh_file), os.path.basename(msh_file) + ".json")
		if not os.path.exists(json_file):
			msh.to_json(json_file, "\t")
