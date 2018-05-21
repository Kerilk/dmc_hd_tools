from inc_noesis import *
import struct

def registerNoesisTypes():
	handle = noesis.register("DMC3 HD Model", ".mod")
	noesis.setHandlerTypeCheck(handle, modCheckType)
	noesis.setHandlerLoadModel(handle, modLoadModel)
	#noesis.logPopup()
	return 1

MOD_HEADER_ID = 0x20444f4d #"MOD "
MOD_HEADER_VER = 0x3f8147ae #1.01
class Batch:
	def __init__(self, bs):
		self.bs = bs
		self.numVertices = bs.readUShort()
		self.texInd = bs.readUShort()
		self.padding = bs.readBytes(12)
		self.offsetPositions = bs.readUInt64()
		self.offsetNormals = bs.readUInt64()
		self.offsetUVs = bs.readUInt64()
		self.offsetUnknown1 = bs.readUInt64()
		self.offsetUnknown2 = bs.readUInt64()
		self.padding2 = bs.readBytes(8)
		self.unknown = bs.readUInt64()
		self.padding3 = bs.readBytes(8)
		self.positions = []
		self.normals = []
		self.uvs = []

	def parseVertices(self):
		bs = self.bs
		bs.seek(self.offsetPositions, NOESEEK_ABS)
		self.positions = bs.readBytes(self.numVertices * 3 * 4)
		bs.seek(self.offsetNormals, NOESEEK_ABS)
		self.normals = bs.readBytes(self.numVertices * 3 * 4)
		bs.seek(self.offsetUVs, NOESEEK_ABS)
		self.uvs = bs.readBytes(self.numVertices * 2 * 2)
		return 1


class Mesh:
	def __init__(self, bs):
		self.bs = bs
		self.numBatches = bs.readUByte()
		self.unknown = bs.readUByte()
		self.numVertices = bs.readUShort()
		self.padding = bs.readUInt()
		self.offsetBatches = bs.readUInt64()
		self.flags = bs.readUInt()
		self.padding2 = bs.readBytes(28)
		self.x = bs.readFloat()
		self.y = bs.readFloat()
		self.z = bs.readFloat()
		self.radius = bs.readFloat()
		self.batches = []

	def parseBatches(self):
		bs = self.bs
		bs.seek(self.offsetBatches, NOESEEK_ABS)
		for _ in range(self.numBatches):
			self.batches.append( Batch(bs) )
		return 1

	def parseVertices(self):
		for b in self.batches:
			b.parseVertices()

class ModFile:
	def __init__(self, bs):
		self.bs = bs
		self.numMeshes = 0
		self.numBones = 0
		self.numTex = 0
		self.numUnknown = 0
		self.unknown = 0
		self.unknown2 = 0
		self.offsetBoneStruct = 0
		self.meshes = []

	def parseHeader(self):
		bs = self.bs
		if bs.getSize() < 64:
			return 0
		bs.seek(0, NOESEEK_ABS)
		iden = bs.readInt()
		if iden != MOD_HEADER_ID:
			return 0
		ver = bs.readInt()
		if ver != MOD_HEADER_VER:
			return 0
		bs.seek(0x10, NOESEEK_ABS)
		self.numMeshes = bs.readUByte()
		self.numBones = bs.readUByte()
		self.numTex = bs.readUByte()
		self.numUnknown = bs.readUByte()
		self.unknown = bs.readUInt()
		self.unknown2 = bs.readUInt64()
		self.offsetBoneStruct = bs.readUInt64()
		return 1

	def parseMeshes(self):
		bs = self.bs
		bs.seek(0x40, NOESEEK_ABS)
		for _ in range(self.numMeshes):
			self.meshes.append( Mesh(bs) )
		return 1

	def parseBatches(self):
		for m in self.meshes:
			m.parseBatches()
		return 1

	def parseVertices(self):
		for m in self.meshes:
			m.parseVertices()
		return 1




def modCheckType(data):
	mod = ModFile(NoeBitStream(data))
	if mod.parseHeader() == 0:
		return 0
	return 1

def modLoadModel(data, mdlList):
	noesis.logPopup()
	mod = ModFile(NoeBitStream(data))
	if mod.parseHeader() == 0:
		return 0
	mod.parseMeshes()
	mod.parseBatches()
	mod.parseVertices()
	ctx = rapi.rpgCreateContext()
	rapi.rpgSetOption(noesis.RPGOPT_BIGENDIAN, 0)
	i = 0
	for m in mod.meshes:
		j = 0
		for b in m.batches:
			print(str(i) + "-" + str(j))
			rapi.rpgSetName(str(i) + "-" + str(j))
			rapi.rpgBindPositionBuffer(b.positions, noesis.RPGEODATA_FLOAT, 12)
			rapi.rpgBindNormalBuffer(b.normals, noesis.RPGEODATA_FLOAT, 12)
			rapi.rpgBindUV1Buffer(b.uvs, noesis.RPGEODATA_USHORT, 4)
			indexes = list(range(b.numVertices))
			triangles = struct.pack("<"+str(len(indexes))+"H",*indexes)
			rapi.rpgCommitTriangles(triangles, noesis.RPGEODATA_USHORT, len(indexes), noesis.RPGEO_TRIANGLE_STRIP, 1)
			rapi.rpgClearBufferBinds()
			j = j + 1
		i = i + 1
	mdl = rapi.rpgConstructModelSlim()
	mdlList.append(mdl)
	return 1
