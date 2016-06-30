#!/home/wilmer/anaconda3/bin/python

__author__ = 'wilmer'
try:
    import mkl
    have_mkl = True
    print("Running with MKL Acceleration")
except ImportError:
    have_mkl = False
    print("Running with normal backends")

from data import *
import gurobipy as grb
import numpy as np
import scipy.io as sio
import matplotlib.pyplot as plt
import sys
import scipy.sparse as sps
import os
import pickle

## Class definition of the gurobi object that handles creation and execution of the model
# Original template from Troy Long.
class tomotherapyNP(object):
    def __init__(self, datastructure):
        print('Reading in data...', end="")
        self.data = datastructure
        print('done')
        print('Constructing Gurobi model object...', end="")
        self.mod = grb.Model()
        self.mod.params.threads = 4
        print('done')
        print('Building main decision variables (dose, binaries).')
        self.minDoseConstraints = []
        self.maxDoseConstraints = []
        self.buildVariables()
        print('Main variables and dose done')

    ## Wrapper for the optimize function
    def solveModel(self):
        self.mod.optimize()

    ## This function builds variables to be included in the model
    def buildVariables(self):
        # Addition of t variables. All terms according to the terminology in the writeup
        ## IntensityVariable
        self.yVar = self.mod.addVar(lb = 0.0, ub = self.data.maxIntensity, obj=0.0, vtype=grb.GRB.CONTINUOUS,
                                    name="intensity", column=None)
        ## Time variable
        self.timeVars = [None] * (self.data.N * self.data.K)
        ## Binary Variable. I call it delta in the writeup
        self.binaryVars = [None] * ((self.data.N * self.data.K) + self.data.N)
        ## xi Variables. Helper variables to create a continuous binary variable
        self.xiVars = [None] * (self.data.N * self.data.K)
        ## zeta Variables. Helper variables to create a continuous binary variable
        self.zetaVars = [None] * (self.data.N * self.data.K)
        self.gammaplusVars = [None] * (self.data.N * self.data.K)
        self.gammaminusVars = [None] * (self.data.N * self.data.K)
        print('Building Variables related to dose constraints...', end=" ")
        for k in range(0, self.data.K):
            for i in range(0, self.data.N):
                self.timeVars[i + k * self.data.N] = self.mod.addVar(lb=0.0, ub=1.0, obj=0.0, vtype=grb.GRB.CONTINUOUS,
                                                                     name="t_{" + str(i) + "," + str(k) + "}",
                                                                     column=None)
                self.xiVars[i + k * self.data.N] = self.mod.addVar(lb=0.0, ub=grb.GRB.INFINITY, obj=0.0,
                                                                   vtype=grb.GRB.CONTINUOUS,
                                                                   name="xi_{" + str(i) + "," + str(k) + "}",
                                                                   column=None)
                self.zetaVars[i + k * self.data.N] = self.mod.addVar(lb=0.0, ub=grb.GRB.INFINITY, obj=0.0,
                                                                     vtype=grb.GRB.CONTINUOUS,
                                                                     name="zeta_{" + str(i) + "," + str(k) + "}",
                                                                     column=None)
                self.gammaplusVars[i + k * self.data.N] = self.mod.addVar(lb=0.0, ub=grb.GRB.INFINITY, obj=0.0,
                                                                     vtype=grb.GRB.CONTINUOUS,
                                                                     name="gammaplus_{" + str(i) + "," + str(k) + "}",
                                                                     column=None)
                self.gammaminusVars[i + k * self.data.N] = self.mod.addVar(lb=0.0, ub=grb.GRB.INFINITY, obj=0.0,
                                                                     vtype=grb.GRB.CONTINUOUS,
                                                                     name="gammaminus_{" + str(i) + "," + str(k) + "}",
                                                                     column=None)
                self.binaryVars[i + k * self.data.N] = self.mod.addVar(lb = 0.0, ub=1.0, obj=0.0, vtype=grb.GRB.BINARY,
                                                                       name="binary_{" + str(i) + "," + str(k) + "}",
                                                                       column=None)
        ## Initialize extra members of binaryvars that are needed. Since there's an extra edge (see writeup)
        for i in range(0, self.data.N):
            self.binaryVars[i + self.data.K * self.data.N] = self.mod.addVar(lb=0.0, ub=1.0, obj=0.0,
                                                                                    vtype=grb.GRB.BINARY,
                                                                                    name="binary_{" + str(i) +
                                                                                         ", extramember}",
                                                                                    column=None)

        ## This is the variable that will appear in the $z_{j}$ constraint. One per actual voxel in small space.
        self.zeeVars = [None] * (self.data.smallvoxelspace)
        for i in range(0, self.data.smallvoxelspace):
            self.zeeVars[i] = self.mod.addVar(lb=0.0, ub=grb.GRB.INFINITY, obj=1.0, vtype=grb.GRB.CONTINUOUS,
                                                                     name="zee_{" + str(i) + "}",
                                                                     column=None)
        # Lazy update of gurobi
        self.mod.update()
        print('done')
        ## Add some constraints
        self.absoluteValueRemovalConstraint = [None] * (self.data.N * self.data.K)
        self.xiconstraint1 = [None] * (self.data.N * self.data.K)
        self.xiconstraint2 = [None] * (self.data.N * self.data.K)
        self.xiconstraint3 = [None] * (self.data.N * self.data.K)
        self.zetaconstraint1 = [None] * (self.data.N * self.data.K)
        self.zetaconstraint2 = [None] * (self.data.N * self.data.K)
        self.zetaconstraint3 = [None] * (self.data.N * self.data.K)
        print('Building Secondary constraints; binaries, xi, zeta...', end="")
        for k in range(0, self.data.K):
            print(str(k) + " ,", end="")
            for i in range(0, self.data.N):
                self.absoluteValueRemovalConstraint[i + k * self.data.N] = self.mod.addConstr(
                    self.binaryVars[i + (k + 1) * self.data.N] - self.binaryVars[i + k * self.data.N],
                    grb.GRB.EQUAL,
                    self.gammaplusVars[i + k * self.data.N] - self.gammaminusVars[i + k * self.data.N],
                    name="rmabs_{" + str(i) + "," + str(k) + "}")
                self.xiconstraint1[i + k * self.data.N] = self.mod.addConstr(
                    self.xiVars[i + k * self.data.N],
                    grb.GRB.LESS_EQUAL,
                    self.data.fractionUB * self.binaryVars[i + k * self.data.N],
                    name="xiconstraint1_{" + str(i) + "," + str(k) + "}")
                self.xiconstraint2[i + k * self.data.N] = self.mod.addConstr(
                    self.xiVars[i + k * self.data.N],
                    grb.GRB.LESS_EQUAL,
                    self.timeVars[i + k * self.data.N],
                    name="xiconstraint2_{" + str(i) + "," + str(k) + "}")
                self.xiconstraint3[i + k * self.data.N] = self.mod.addConstr(
                    self.xiVars[i + k * self.data.N],
                    grb.GRB.GREATER_EQUAL,
                    self.timeVars[i + k * self.data.N] - (1 - self.binaryVars[i + k * self.data.N]) * self.data.fractionUB,
                    name="xiconstraint3_{" + str(i) + "," + str(k) + "}")
                self.zetaconstraint1[i + k * self.data.N] = self.mod.addConstr(
                    self.zetaVars[i + k * self.data.N],
                    grb.GRB.LESS_EQUAL,
                    self.data.fractionUB * self.binaryVars[i + (k + 1) * self.data.N],
                    name="zetaconstraint1_{" + str(i) + "," + str(k) + "}")
                self.zetaconstraint2[i + k * self.data.N] = self.mod.addConstr(
                    self.zetaVars[i + k * self.data.N],
                    grb.GRB.LESS_EQUAL,
                    self.timeVars[i + k * self.data.N],
                    name="zetaconstraint2_{" + str(i) + "," + str(k) + "}")
                self.zetaconstraint3[i + k * self.data.N] = self.mod.addConstr(
                    self.zetaVars[i + k * self.data.N],
                    grb.GRB.GREATER_EQUAL,
                    self.timeVars[i + k * self.data.N] - (1 - self.binaryVars[i + (k + 1) * self.data.N]) * self.data.fractionUB,
                    name="zetaconstraint3_{" + str(i) + "," + str(k) + "}")
        print('\ndone')
        self.zeeconstraints = [None] * (self.data.smallvoxelspace)
        print('here')
        ## Create a unique list of voxels (smallvoxelspace steps but living in bigvoxelspace)
        # This vector should be used later and is the standard ordering of particles in smallvoxelspace.
        uniquevoxels = np.unique(self.data.voxels)
        print('here')
        i = 0
        print('creating primary dose constraints...', end="")
        # Create all the dose constraints
        for voxel in uniquevoxels:
            # Find locations with value corresponding to voxel
            positions = np.where(voxel == self.data.voxels)[0]
            expr = grb.QuadExpr()
            for i, p in zip(range(0, len(positions)), positions):
                abixel = self.data.bixels[p]
                expr += self.data.Dijs[abixel] * self.xiVars[abixel] * self.yVar
                expr += self.data.Dijs[abixel] * self.zetaVars[abixel] * self.yVar
            self.zeeconstraints[i] = self.mod.addQConstr(self.zeeVars[i], grb.GRB.EQUAL, expr, name = "DoseConstraint" +
                                                                                                      str(i))
            i += 1

        # Make a lazy update of this last set of constraints
        self.mod.update()
        print('done')
        # Update the objective function.
        # Create a variable that will be the minimum dose to a PTV.
        print('creating VOI constraints and constraints directly associated with the objective...', end="")
        self.minDosePTVVar = self.mod.addVar(lb=0.0, ub=grb.GRB.INFINITY, obj=0.0, vtype=grb.GRB.CONTINUOUS,
                                                                     name="minDosePTV", column=None)
        self.mod.update()
        for i in range(0, self.data.smallvoxelspace):
            # Constraint on minimum radiation if this is a tumor
            if self.data.mask[self.data.SmalltoBig[0][i]] in self.data.TARGETList:
                self.minDoseConstraints.append(self.mod.addConstr(self.minDosePTVVar, grb.GRB.LESS_EQUAL, self.zeeVars[i]))
            # Constraint on maximum radiation to the OAR
            if self.data.mask[self.data.SmalltoBig[0][i]] in self.data.OARList:
                self.maxDoseConstraints.append(self.mod.addConstr(self.zeeVars[i], grb.GRB.LESS_EQUAL, self.data.OARMAX))
        self.mod.update()
        print('done')
        # Set the objective value
        print('Setting up and launching the optimization...', end="")
        objexpr = grb.LinExpr()
        objexpr.addTerms(np.array([1.0 for element in range(len(self.gammaplusVars))], dtype=np.int32), self.gammaplusVars)
        objexpr.addTerms(np.array([1.0 for element in range(len(self.gammaplusVars))], dtype=np.int32), self.gammaminusVars)
        objexpr -= self.minDosePTVVar
        #for k in range(0, self.data.K):
        #    for i in range(0, self.data.N):
        #        objexpr += self.gammaplusVars[i + k * self.data.N] + self.gammaminusVars[i + k * self.data.N]
        self.mod.setObjective(objexpr, 1.0) #1.0 expresses minimization. It is the model sense.
        self.mod.update()
        self.mod.optimize()
        print('done')

    def plotDVH(self, saveNameTag='', plotFull=False, showPlot=False, differentVoxelMap=''):
        if differentVoxelMap != '':
            voxMap = np.loadtxt(self.data.dataDirectory + differentVoxelMap, dtype='int32')
            voxDict = {}
            for t in self.data.targetIndices:
                voxDict[t] = np.where(voxMap == t)[0]
            for o in self.data.oarIndices:
                voxDict[o] = np.where(voxMap == o)[0]
        else:
            voxMap = np.loadtxt(self.data.dataDirectory + self.data.voxelMapDVH, dtype='int32')
            voxDict = {}
            for t in self.data.targetIndices:
                voxDict[t] = np.where(voxMap == t)[0]
            for o in self.data.oarIndices:
                voxDict[o] = np.where(voxMap == o)[0]
        dose = np.array([self.doseVars[j].X for j in range(self.data.nVox)])
        plt.clf()
        for index, sValues in voxDict.iteritems():
            if plotFull:
                sVoxels = sValues
            else:
                if not len(sValues) > 0:
                    continue
                sVoxels = sValues
            hist, bins = np.histogram(dose[sVoxels], bins=100)
            dvh = 1. - np.cumsum(hist) / float(sVoxels.shape[0])
            plt.plot(bins[:-1], dvh, label="struct " + str(index), linewidth=2)
        lgd = plt.legend(fancybox=True, framealpha=0.5, bbox_to_anchor=(1.05, 1), loc=2)
        plt.title('DVH')
        plt.savefig(self.data.outputDirectory + saveNameTag + '_' + self.data.outputFilename[:-4] + '.png',
                        bbox_extra_artists=(lgd,), bbox_inches='tight')
        if showPlot:
            plt.show()

    def outputSolution(self):
        outDict = {}
        outDict['yVector'] = np.array([self.cpBinaryVars[i].X for i in range(self.data.nCP)])
        outDict['doseVector'] = np.array([self.doseVars[j].X for j in range(self.data.nVox)])
        outDict['obj'] = self.mod.objVal

        if self.data.modType == 'modulated':
            outDict['intensities'] = np.array([self.cpBilinearVars[i].X for i in range(self.data.nCP)])

        # check if directory exists
        if not os.path.exists(self.data.outputDirectory):
            os.makedirs(self.data.outputDirectory)
        sio.savemat(self.data.outputDirectory + self.data.outputFilename, outDict)

## Function that reads the files produced by Weiguo
def getvector(necfile,dtype):
    with open(necfile, 'rb') as f:
        try:
            data = np.fromfile(f, dtype=dtype)
        finally:
            f.close()
    return(data)

## This function creates a sparse matrix
def sparseWrapper(bixels, voxels, Dijs, mask, totalbeamlets, totalVoxels):
    D = sps.csc_matrix((Dijs, (bixels, voxels)), shape=(totalbeamlets, totalVoxels))
    return(D)

class tomodata:
    ## Initialization of the data
    def __init__(self):
        ## C Value in the objective function
        self.C = 1.0
        ## M value. A large value that variable t will not reach (t in this case is from 0 to 1)
        self.fractionUB = 1.0
        self.maxIntensity = 10.0
        self.N = 80
        ## Number of control points (every 2 degrees)
        self.K = 178
        ## Total number of beamlets
        self.totalbeamlets = self.K * self.N
        ## Dimensions of the 2-Dimensional screen
        self.dimX = 256
        self.dimY = 256
        ## OARMAX is maximum dose tolerable for organs. 10 in this case
        self.OARMAX = 10
        ## Total number of voxels in the phantom
        self.totalVoxels = self.dimX * self.dimY
        print('Read vectors...', end="")
        #self.readWilmersCase()
        self.readWeiguosCase()
        print('done')
        ## This is the total number of voxels that there are in the body. Not all voxels from all directions
        self.smallvoxelspace = len(np.unique(self.voxels))
        self.SmallToBigCreator()

    ## Create a map from big to small voxel space
    def SmallToBigCreator(self):
        self.SmalltoBig = np.where(0 != self.mask)

    def readWeiguosCase(self):
        self.bixels = getvector('data\\Bixels_out.bin', np.int32)
        self.voxels = getvector('data\\Voxels_out.bin', np.int32)
        self.Dijs = getvector('data\\Dijs_out.bin', np.float32)
        self.mask = getvector('data\\optmask.img', np.int32)
        self.OARList = [2, 3]
        self.TARGETList = [256]

    def readWilmersCase(self):
        self.bixels = getvector('data\\myBixels_out.bin', np.int32)
        self.voxels = getvector('data\\myVoxels_out.bin', np.int32)
        self.Dijs = getvector('data\\myDijs_out.bin', np.float32)
        self.mask = getvector('data\\myoptmask.img', np.int32)
        with open('C:/Users/S170452/PycharmProjects/Tomotherapy-Without-Pulse/data/mydict.pckl', 'rb') as ff:
            dictdata = pickle.load(ff)
        self.K = dictdata['K']
        self.N = dictdata['N']
        self.OARList = dictdata['OARIDs']
        self.TARGETList = dictdata['TARGETIDs']

## Number of beamlets in each gantry. Usually 64 but Weiguo uses 80
dataobject = tomodata()
tomoinstance = tomotherapyNP(dataobject)
