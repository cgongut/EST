import projection
import numpy as np
import scipy.special as sp
import scipy.linalg as spla
import scipy.sparse as sparse
import matplotlib.pyplot as pl
import pyiacsun as ps
from ipdb import set_trace as stop
import seaborn as sns
import uuid
import glob
import wavefront as wf

def even(x):
    return x%2 == 0

class tomography(object):
    """This class defines an atmosphere that can be used to generate synthetic MCAO observations
    and also apply different tomography schemes
    """
    def __init__(self, nStars, nZernike, fov, heights, DTel, verbose=True, numericalProjection=True, addPiston=False):
        """Class creation
        
        Args:
            nStars (int): number of stars used for the MCAO
            nZernike (int): maximum number of Zernike coefficients to use
            fov (float): field-of-view [arcsec]
            heights (float): array of heights to be used [km]
            DTel (float): telescope diameter [m]
            verbose (bool, optional): turn on verbosity
            numericalProjection (bool, optional): use the numerical approach for computing the projection matrix for the footprints
            addPiston (bool, optional): add piston mode
        """
        self.nHeight = len(heights)
        self.nStars = nStars
        self.nZernike = nZernike
        self.fov = fov / 206265.0        # in radians
        self.heights = heights * 1e3
        self.DTel = DTel
        self.verbose = verbose
        self.MComputed = False
        self.numericalProjection = numericalProjection
        self.addPiston = addPiston
        self.noll0 = 1
        if (not self.addPiston):
            self.noll0 = 2

        self.DMetapupil = self.DTel + self.heights * self.fov

        self.t = np.zeros((self.nHeight,self.nStars))
        self.beta = np.zeros((self.nHeight,self.nStars))
        self.angle = np.zeros((self.nHeight,self.nStars))

        if (self.verbose):
            print("-------------------------------------------------------------------")
            print(" - Zernike modes: {0}".format(self.nZernike))
            print(" - Number of heights : {0} -> {1} km".format(self.nHeight, self.heights * 1e-3))
            print(" - FOV: {0} arcsec".format(206265.*self.fov))
            print(" - Number of stars : {0}".format(self.nStars))
            print("-------------------------------------------------------------------")

        for i in range(self.nHeight):            
            for j in range(self.nStars):
                self.t[i,j] = (self.heights[i] * self.fov) / self.DMetapupil[i]
                self.beta[i,j] = self.DMetapupil[i] / self.DTel
                self.angle[i,j] = j * 2.0 * np.pi / self.nStars

        
        if (self.projectionExists() == 0):
            if (self.verbose):
                print("Projection matrix does not exist")
            self.computeProjection()

        self.aStack = {}
        self.a = {}

    def projectionExists(self):
        """Check whether a projection matrix exists
        
        Returns:
            bool: True/False
        """
        files = glob.glob('matrices/transformationMatrices*.npz')
        for f in files:
            out = np.load(f)
            heights = out['arr_1']
            nStars = out['arr_2']
            nZernike = out['arr_3']
            fov = out['arr_4']
            DTel = out['arr_5']
            ind = np.where(np.in1d(heights, self.heights))[0]
            if (len(ind) == self.nHeight):
                if (nStars == self.nStars and nZernike >= self.nZernike and 
                    fov == self.fov and DTel == self.DTel):
                    self.M = out['arr_0'][0:self.nZernike,0:self.nZernike,ind,:]
                    if (self.verbose):
                        print("Projection matrix exists : {0}".format(f))
                        print(" - Zernike modes: {0}".format(self.nZernike))
                        print(" - Number of heights : {0} -> {1} km".format(self.nHeight, self.heights * 1e-3))
                        print(" - FOV: {0} arcsec".format(206265.*self.fov))
                        print(" - Number of stars : {0}".format(self.nStars))
                        self.MComputed = True
                        self.stackProjection()
                    return True
                
        return False

    def plotPupils(self):
        """Plot the pupils
                
        """
        ncols = int(np.ceil(np.sqrt(self.nHeight)))
        nrows = int(np.ceil(self.nHeight / ncols))
        cmap = sns.color_palette()
        pl.close('all')

        f, ax = pl.subplots(ncols=ncols, nrows=nrows, figsize=(2*ncols,2*nrows))
        ax = ax.flatten()
        for i in range(self.nHeight):
            radiusMetapupil = self.DMetapupil[i] / 2.0
            circle = pl.Circle((0,0), radiusMetapupil, fill=False, linewidth=2, axes=ax[i])
            ax[i].add_artist(circle)
            ax[i].set_xlim([-0.7*self.DMetapupil[i],0.7*self.DMetapupil[i]])
            ax[i].set_ylim([-0.7*self.DMetapupil[i],0.7*self.DMetapupil[i]])
            ax[i].set_title('h={0} km'.format(self.heights[i] / 1e3))
            for j in range(self.nStars):
                radiusCircle = radiusMetapupil / self.beta[i,j]
                xCircle = radiusMetapupil * self.t[i,j] * np.cos(self.angle[i,j])
                yCircle = radiusMetapupil * self.t[i,j] * np.sin(self.angle[i,j])
                circle = pl.Circle((xCircle,yCircle), radiusCircle, fill=False, axes=ax[i], linewidth=2, color=cmap[j])
                ax[i].add_artist(circle)

    def computeProjection(self):
        """Compute the projection matrix for the heights and number of stars defined
        
        Returns:
            None
        """
        if (not self.MComputed):
            self.M = np.zeros((self.nZernike,self.nZernike,self.nHeight,self.nStars))
            for i in range(self.nHeight):
                print("\n**********************\n")
                print("Height: {0}/{1}\n".format(i+1,self.nHeight))
                print("**********************\n")
                for j in range(self.nStars):
                    print("\n  - Star: {0}/{1}".format(j+1,self.nStars))
                    if (self.numericalProjection):
                        self.M[:,:,i,j] = projection.zernikeProjectionMatrixNumerical(self.nZernike, self.beta[i,j], self.t[i,j], self.angle[i,j], verbose=True, radius=128, includePiston=False)
                    else:
                        self.M[:,:,i,j] = projection.zernikeProjectionMatrix(self.nZernike, self.beta[i,j], self.t[i,j], self.angle[i,j], verbose=True, includePiston=False)
            np.savez('matrices/transformationMatrices_{0}.npz'.format(uuid.uuid4()), self.M, self.heights, self.nStars, self.nZernike, self.fov, self.DTel)
            self.stackProjection()

    def stackProjection(self):
        """Stack the projection matrix to take all heights into account
        
        Returns:
            None
        """
        self.MStack = np.zeros((self.nZernike*self.nStars, self.nZernike*self.nHeight))
        for i in range(self.nHeight):
            for j in range(self.nStars):
                left = i*self.nZernike
                right = (i+1)*self.nZernike
                up = j*self.nZernike
                down = (j+1)*self.nZernike
                self.MStack[up:down,left:right] = self.M[:,:,i,j]

    def generateTurbulentZernikesKolmogorov(self, r0, keepOnly=None):
        """Generate the covariance matrix for the Zernike coefficients for a given value of r0 using Kolmogorov statistics
        
        Args:
            r0 (float): Fried radius [m]
        
        Returns:
            None
        """
        self.covariance = np.zeros((self.nZernike,self.nZernike))
        for i in range(self.nZernike):
            ni, mi = wf.nollIndices(i+self.noll0)
            for j in range(self.nZernike):
                nj, mj = wf.nollIndices(j+self.noll0)
                if (even(i - j)):
                    if (mi == mj):
                        phase = (-1.0)**(0.5*(ni+nj-2*mi))
                        t1 = np.sqrt((ni+1)*(nj+1)) * np.pi**(8.0/3.0) * 0.0072 * (self.DTel / r0)**(5.0/3.0)
                        t2 = sp.gamma(14./3.0) * sp.gamma(0.5*(ni+nj-5.0/3.0))
                        t3 = sp.gamma(0.5*(ni-nj+17.0/3.0)) * sp.gamma(0.5*(nj-ni+17.0/3.0)) * sp.gamma(0.5*(ni+nj+23.0/3.0))
                        self.covariance[i,j] = phase * t1 * t2 / t3

        self.a['Original'] = np.random.multivariate_normal(np.zeros(self.nZernike), self.covariance, size=(self.nHeight)).T

# Keep only the heights that we want
        if (keepOnly != None):
            for i in range(self.nHeight):
                if (self.heights[i]/1e3 not in keepOnly):
                    self.a['Original'][:,i] = 0.0

        self.aStack['Original'] = self.a['Original'].T.flatten()


    def generateTurbulentZernikesVonKarman(self, r0, L0):
        """Generate the covariance matrix for the Zernike coefficients for a given value of r0 using von Karman statistics
        
        Args:
            r0 (float): Fried radius [m]
            L0 (float): outer scale [m]
        
        Returns:
            None
        """
        self.covariance = np.zeros((self.nZernike,self.nZernike))
        for i in range(self.nZernike):
            ni, mi = wf.nollIndices(i+self.noll0)
            for j in range(self.nZernike):
                nj, mj = wf.nollIndices(j+self.noll0)
                if (even(i - j)):
                    if (mi == mj):
                        phase = (-1.0)**(0.5*(ni+nj-2*mi))
                        t1 = np.sqrt((ni+1)*(nj+1)) * np.pi**(8.0/3.0) * 1.16 * (self.DTel / r0)**(5.0/3.0)

                        for k in range(50):
                            phase2 = (-1.0)**k / np.math.factorial(k) * (np.pi*self.DTel / L0)**(2.0*k+ni+nj-5.0/3.0)
                            t2 = sp.gamma(k+0.5*(3+ni+nj)) * sp.gamma(k+2+0.5*(ni+nj)) * sp.gamma(k+1+0.2*(ni+nj)) * sp.gamma(5./6.-k-0.5*(ni+nj))
                            t3 = sp.gamma(3+k+ni+nj) * sp.gamma(2+k+ni) * sp.gamma(2+k+nj)

                            phase3 = (np.pi*self.DTel / L0)**(2.0*k)
                            t4 = sp.gamma(0.5*(ni+nj)-5./6.-k) * sp.gamma(k+7./3.) * sp.gamma(k+17/6) * sp.gamma(k+11/6)
                            t5 = sp.gamma(0.5*(ni+nj)+23/6.+k) * sp.gamma(0.5*(ni-nj)+17/6.+k) * sp.gamma(0.5*(ni-nj)+17/6.+k)
                            self.covariance[i,j] += phase * t1 * (phase2 * t2/t3 + phase3 * t4/t5)

        self.a['Original'] = np.random.multivariate_normal(np.zeros(self.nZernike), self.covariance, size=(self.nHeight)).T        
        self.aStack['Original'] = self.a['Original'].T.flatten()

    def generateWFS(self):
        """Generate a WFS taking into account all heights
        
        Returns:
            float: array of Zernike coefficients measured in all WFS
        """
        return self.MStack @ self.aStack['Original']
        # self.bStack += np.random.normal(loc=0.0, scale=0.05, size=self.bStack.shape)


    def solveSVD(self, b, regularize=False):
        """Solve the tomography using SVD
        
        Args:
            b (TYPE): array of WFS measurements
            regularize (bool, optional): apply Tikhonov regularization using the covariance matrix of the Zernike coefficients
        
        Returns:
            None
        """
        if (regularize):
            invCov = np.linalg.inv(self.covariance)
            matrixList = [invCov for i in range(self.nHeight)]
            cov = spla.block_diag(*matrixList)
            AInv = np.linalg.inv(self.MStack.T@self.MStack + cov.T@cov)
        else:
            AInv = np.linalg.inv(self.MStack.T@self.MStack)

        x = AInv @ self.MStack.T @ b
        
        self.aStack['SVD'] = x
        self.a['SVD'] = self.aStack['SVD'].reshape((self.nHeight,self.nZernike)).T

    def _g(self, x):
        return self.mu * np.linalg.norm(x, 1)

    def _proxgHeight(self, x, t):
        coef = x.reshape((self.nHeight,self.nZernike))
        coefOut = np.copy(coef)
        for i in range(self.nZernike):            
            # coefOut[:,i] = ps.sparse.proxes.prox_l0Largest(coef[:,i], 3)
            coefOut[:,i] = ps.sparse.proxes.prox_l1(coef[:,i], t*self.mu)

        return coefOut.flatten()

    def _proxg(self, x, t):
        return ps.sparse.proxes.prox_l1(x ,t*self.mu)

    def solveFASTA(self, b):        
        """Solve the tomography using l1 regularization
        
        Args:
            b (TYPE): array of WFS measurements
        
        Returns:
            None    
        """
        L = np.linalg.norm(self.MStack, 2)**2
        
        self.MStackStar = self.MStack.T

# Define the operators we need
        A = lambda x : self.MStack @ x
        At = lambda x : self.MStackStar @ x

# ||x-b||^2
        f = lambda x : 0.5 * np.linalg.norm(x - b, 2)**2
        gradf = lambda x : x - b
        
# Regularization parameter
        mus = [1e-5]
        
        values = np.zeros_like(self.aStack['Original'])

        for mu in mus:
            self.mu = mu                        
            out = ps.sparse.fasta(A, At, f, gradf, self._g, self._proxg, values, tau=1.32/L, verbose=True, tol=1e-12, maxIter=60000, accelerate=True, backtrack=False, adaptive=False)
            values = out.optimize()

        self.aStack['L1'] = values
        self.a['L1'] = self.aStack['L1'].reshape((self.nHeight,self.nZernike)).T

    # def solveZeroSR1(self, b):
    #     L = np.linalg.norm(self.MStack, 2)**2
        
    #     self.MStackStar = self.MStack.T

    #     A = lambda x : self.MStack @ x
    #     At = lambda x : self.MStackStar @ x
    #     f = lambda x : 0.5 * np.linalg.norm(x - b, 2)**2
    #     gradf = lambda x : x - b
        
    #     mus = [3e-4]
        
    #     values = np.zeros_like(self.aStack['Original'])

    #     for mu in mus:
                        
    #         prox = lambda x0, d, u, varargin = None : ps.sparse.proxes_rank1.prox_rank1_l1(x0, d, u, mu)
    #         h = lambda x : mu * np.linalg.norm(x,1)
    #         fcnGrad = lambda x : ps.sparse.smooth.normSquared(x, A, At, np.atleast_2d(self.bStack).T)
    #         opts = {'tol': 1e-10, 'grad_tol' : 1e-6, 'nmax' : 10000, 'verbose' : False, 'N' : self.nZernike*self.nHeight, 'L': L, 'verbose': 25}

    #         values, nIteration, stepSizes = ps.sparse.zeroSR1(fcnGrad, h, prox, opts)

    #         # print(f(A(values)) + g(values))
    #         # print(f(A(self.aStack['SVD'])))
    #         # stop()            
        
    #     self.aStack['L1'] = values
    #     self.a['L1'] = self.aStack['L1'].reshape((self.nHeight,self.nZernike)).T

def plotResults(forward, inversion):
    ncols = forward.nHeight
    nrows = 3
    cmap = sns.color_palette()

        # f, ax = pl.subplots(ncols=ncols, nrows=nrows, figsize=(3*ncols,3*nrows))        
        # for i in range(self.nHeight):
        #     w, n, m = wf.zernike(0, npix=int(2*128))
        #     w *= 0.0
        #     wOrig = np.zeros_like(w)
        #     for j in range(self.nZernike):
        #         z, n, m = wf.zernike(j+1, npix=int(2*128))
        #         w += self.aInferred['SVD'][j,i] * z
        #         wOrig += self.a[j,i] * z

        #     ps.plot.tvframe(w, ax=ax[0,i])
        #     ps.plot.tvframe(wOrig, ax=ax[1,i])
        #     ps.plot.tvframe(w - wOrig, ax=ax[2,i])

    pl.close('all')

    f, ax = pl.subplots(nrows=2, ncols=1, figsize=(12,10))
    ax[0].plot(inversion.aStack['SVD'], label='SVD')
    ax[0].plot(forward.aStack['Original'], label='Original')
    ax[1].plot(inversion.aStack['L1'], label='l1')
    ax[1].plot(forward.aStack['Original'], label='Original')
    ax[0].legend()
    ax[1].legend()

np.random.seed(123)
sns.set_style("dark")
nStars = 3
nZernike = 30
fov = 60.0
r0 = 0.15
DTel = 4.0

heights = np.arange(31)
# heights = np.asarray([0.0, 4.0, 8.0])
forward = tomography(nStars, nZernike, fov, heights, DTel)
forward.generateTurbulentZernikesKolmogorov(r0, keepOnly=[0.0,4.0,16.0])
bMeasured = forward.generateWFS()


heights = np.arange(31)
inversion = tomography(nStars, nZernike, fov, heights, DTel)
inversion.generateTurbulentZernikesKolmogorov(r0)
inversion.solveSVD(bMeasured)
inversion.solveFASTA(bMeasured)

plotResults(forward, inversion)