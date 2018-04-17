# -------------------------------------------------------------------
## The CMP
# -------------------------------------------------------------------
# Set definitions
param numProjections > 0;
param U > 0;
param numLeaves integer > 0;
param projecs > 0;
param ko integer > 0;
param kc integer > 0;
param numvoxels > 0;

param maxkcko := max(ko, kc);
# Set definitions
set PROJECTIONS = {-maxkcko..((numProjections - 1) + maxkcko)};
set PROJECTIONSM1 = {-maxkcko..((numProjections - 2) + maxkcko)};
set PROJECTIONSSHORT = {0..(numProjections - 1)};
set PROJECTIONSSHORTM1 = {0..(numProjections - 2)};
set LOTSET = {0..(kc-1)};
set LCTSET = {0..(ko-1)};
set LEAVES = {0..(numLeaves - 1)};
set VOXELS;
set KNJMPARAMETERS within {l in LEAVES, p in PROJECTIONS, j in VOXELS};

# Parameters
param D {KNJMPARAMETERS} >= 0;
param thethreshold {VOXELS} >= 0;
param quadHelperOver {VOXELS} >= 0;
param quadHelperUnder {VOXELS} >= 0;
param yparam;
#50 msecs is 0.05;

# Variables
var z {j in VOXELS} >= 0;
var z_plus {j in VOXELS} >= 0;
var z_minus {j in VOXELS} >= 0;
var t {l in LEAVES, p in PROJECTIONS} >= 0, <= 0.3;

# Objective
minimize ObjectiveFunction: sum {j in VOXELS} (quadHelperUnder[j] * z_minus[j] * z_minus[j] + quadHelperOver[j] * z_plus[j] * z_plus[j]);
# -------------------------------------------------------------------
subject to positive_only {j in VOXELS}: z_plus[j] - z_minus[j] = z[j] - thethreshold[j];
subject to doses_to_j_yparam {j in VOXELS}: z[j] = yparam * sum{ (l,p,j) in KNJMPARAMETERS}( D[l,p,j] * t[l,p]);