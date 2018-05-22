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
		self.offsetBoneIndexes = bs.readUInt64()
		self.offsetBoneWeights = bs.readUInt64()
		self.padding2 = bs.readBytes(8)
		self.unknown = bs.readUInt64()
		self.padding3 = bs.readBytes(8)
		self.positions = ""
		self.normals = ""
		self.boneIndexes = ""
		self.boneWeights = ""
		self.uvs = ""
		self.triangles = ""
		self.trianglesIndexCount = 0

	def parseVertices(self):
		bs = self.bs
		bs.seek(self.offsetPositions, NOESEEK_ABS)
		self.positions = bs.readBytes(self.numVertices * 3 * 4)

		bs.seek(self.offsetNormals, NOESEEK_ABS)
		self.normals = bs.readBytes(self.numVertices * 3 * 4)

		bs.seek(self.offsetUVs, NOESEEK_ABS)
		self.uvs = []
		for i in range(self.numVertices):
			self.uvs.append( bs.readShort()/4096.0 )
			self.uvs.append( 1.0 - bs.readShort()/4096.0 )
		self.uvs = struct.pack(str(len(self.uvs))+"f", *self.uvs)


		bs.seek(self.offsetBoneIndexes, NOESEEK_ABS)
		bI = []
		for i in range(self.numVertices):
			bs.readByte()
			bI.append( bs.readByte()//4 )
			bI.append( bs.readByte()//4 )
			bI.append( bs.readByte()//4 )
		self.boneIndexes = struct.pack(str(len(bI))+"b",*bI)

		bs.seek(self.offsetBoneWeights, NOESEEK_ABS)
		boneWeights = []
		triangleSkip = []
		for i in range(self.numVertices):
			w = bs.readUShort()
			triangleSkip.append( (w >> 15) & 1 )
			boneWeights.append( ((w >> 10) & 0x1f) / 31.0 )
			boneWeights.append( ((w >>  5) & 0x1f) / 31.0 )
			boneWeights.append( ((w >>  0) & 0x1f) / 31.0 )
		self.boneWeights = struct.pack("<"+str(len(boneWeights))+"f",*bI)

		triangles = []
		v1 = 0
		v2 = 1
		for i in range(2, self.numVertices):
			v3 = i
			if triangleSkip[i] == 0:
				triangles.append(v2)
				triangles.append(v1)
				triangles.append(v3)
			v1 = v2
			v2 = v3
		self.triangles = struct.pack("<"+str(len(triangles))+"H",*triangles)
		self.trianglesIndexCount = len(triangles)


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

class BoneStruct:
	def __init__(self, bs, numBones):
		base_offset = bs.tell()
		self.bs = bs
		self.numBones = numBones
		self.offsetHierarchy = bs.readUInt()
		self.offsetHierarchyOrder = bs.readUInt()
		self.offsetUnknown = bs.readUInt()
		self.offsetMatrices = bs.readUInt()

		bs.seek(base_offset + self.offsetHierarchy, NOESEEK_ABS)
		self.hierarchy = []
		for i in range(numBones):
			self.hierarchy.append( bs.readByte() )

		bs.seek(base_offset + self.offsetHierarchyOrder, NOESEEK_ABS)
		self.hierarchyOrder = []
		for i in range(numBones):
			self.hierarchyOrder.append( bs.readByte() )

		bs.seek(base_offset + self.offsetUnknown, NOESEEK_ABS)
		self.unknown = []
		for i in range(numBones):
			self.unknown.append( bs.readByte() )

		bs.seek(base_offset + self.offsetMatrices, NOESEEK_ABS)
		self.matrices = []
		for i in range(numBones):
			self.matrices.append( bs.readBytes(32) )

		parents = []
		for i in range(numBones):
			parents.append(-1)
		for i in range(numBones):
			parents[self.hierarchyOrder[i]] = self.hierarchy[i]

		self.bones = []
		for i in range(numBones):
			mat = NoeMat43()
			mat = mat.translate(NoeVec3.fromBytes(self.matrices[i]))
			self.bones.append( NoeBone(i, "bone%03i"%i, mat, None, parents[i]) )
		self.bones = rapi.multiplyBones(self.bones)

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
		self.boneStruct = None

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

	def parseBones(self):
		bs = self.bs
		bs.seek(self.offsetBoneStruct, NOESEEK_ABS)
		self.boneStruct = BoneStruct(bs, self.numBones)


def modCheckType(data):
	mod = ModFile(NoeBitStream(data))
	if mod.parseHeader() == 0:
		return 0
	return 1

def modLoadModel(data, mdlList):
	#noesis.logPopup()
	mod = ModFile(NoeBitStream(data))
	if mod.parseHeader() == 0:
		return 0
	mod.parseMeshes()
	mod.parseBatches()
	mod.parseVertices()
	mod.parseBones()
	ctx = rapi.rpgCreateContext()
	rapi.rpgSetOption(noesis.RPGOPT_BIGENDIAN, 0)
	i = 0
	for m in mod.meshes:
		j = 0
		for b in m.batches:
			#print(str(i) + "-" + str(j))
			rapi.rpgSetName(str(i) + "-" + str(j))
			rapi.rpgBindPositionBuffer(b.positions, noesis.RPGEODATA_FLOAT, 12)
			rapi.rpgBindNormalBuffer(b.normals, noesis.RPGEODATA_FLOAT, 12)
			rapi.rpgBindUV1Buffer(b.uvs, noesis.RPGEODATA_FLOAT, 8)
			rapi.rpgBindBoneIndexBuffer(b.boneIndexes, noesis.RPGEODATA_UBYTE, 3, 3)
			rapi.rpgBindBoneWeightBuffer(b.boneWeights, noesis.RPGEODATA_FLOAT, 12, 3)
			rapi.rpgCommitTriangles(b.triangles, noesis.RPGEODATA_USHORT, b.trianglesIndexCount, noesis.RPGEO_TRIANGLE, 1)
			rapi.rpgClearBufferBinds()
			j = j + 1
		i = i + 1
	mdl = rapi.rpgConstructModel()
	mdl.setBones(mod.boneStruct.bones)
	mdlList.append(mdl)
	return 1
