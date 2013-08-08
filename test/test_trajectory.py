# We assume all lengths in Angstrom. Only important for ASE comparison.
#
import types
import numpy as np
from pwtools.crys import Trajectory, Structure
from pwtools import crys, constants
from pwtools.test.tools import aaae, assert_all_types_equal,\
    assert_attrs_not_none, assert_dict_with_all_types_equal
from pwtools import num
rand = np.random.rand


def get_rand_traj():
    natoms = 10
    nstep = 100
    cell = rand(nstep,3,3)
    stress = rand(nstep,3,3)
    forces = rand(nstep,natoms,3)
    etot=rand(nstep)
    coords_frac = np.random.rand(nstep,natoms,3)
    symbols = ['H']*natoms
    tr = Trajectory(coords_frac=coords_frac,
                    cell=cell,
                    symbols=symbols,
                    forces=forces,
                    stress=stress,
                    etot=etot,
                    timestep=1,
                    )
    return tr


def get_rand_struct():
    natoms = 10
    symbols = ['H']*natoms
    st = Structure(coords_frac=rand(natoms,3),
                   symbols=symbols,
                   forces=rand(natoms,3),
                   cell=rand(3,3),
                   etot=3.14,
                   stress=rand(3,3))
    return st


def test_traj():
    natoms = 10
    nstep = 100
    cell = rand(nstep,3,3)
    stress = rand(nstep,3,3)
    forces = rand(nstep,natoms,3)
    etot=rand(nstep)
    cryst_const = crys.cell2cc3d(cell, axis=0)
    coords_frac = np.random.rand(nstep,natoms,3)
    coords = crys.coord_trans3d(coords=coords_frac,
                                old=cell,
                                new=num.extend_array(np.identity(3),
                                                     nstep,axis=0),
                                axis=1,
                                timeaxis=0)                                                    
    assert cryst_const.shape == (nstep, 6)
    assert coords.shape == (nstep,natoms,3)
    symbols = ['H']*natoms
    
    # automatically calculated:
    #   coords
    #   cell
    #   pressure
    #   velocity (from coords)
    #   temperature (from ekin)
    #   ekin (from velocity)
    traj = Trajectory(coords_frac=coords_frac,
                    cell=cell,
                    symbols=symbols,
                    forces=forces,
                    stress=stress,
                    etot=etot,
                    timestep=1,
                    )
    # Test if all getters work.
    for name in traj.attr_lst:
        print name
        if name not in ['ase_atoms']:
            traj.try_set_attr(name)
            assert getattr(traj, name) is not None, "attr None: %s" %name
            assert eval('traj.get_%s()'%name) is not None, "getter returns None: %s" %name
    aaae(coords_frac, traj.coords_frac)
    aaae(cryst_const, traj.cryst_const)
    aaae(np.trace(stress, axis1=1, axis2=2)/3.0, traj.pressure)
    assert traj.coords.shape == (nstep,natoms,3)
    assert traj.cell.shape == (nstep,3,3)
    assert traj.velocity.shape == (nstep, natoms, 3)
    assert traj.temperature.shape == (nstep,)
    assert traj.ekin.shape == (nstep,)
    assert traj.nstep == nstep
    assert traj.natoms == natoms

    traj = Trajectory(coords_frac=coords_frac,
                    symbols=symbols,
                    cell=cell)
    aaae(coords, traj.coords)
    
    # Cell calculated from cryst_const has defined orientation in space which may be
    # different from the original `cell`, but the volume and underlying cryst_const
    # must be the same.
    traj = Trajectory(coords_frac=coords_frac,
                    symbols=symbols,
                    cryst_const=cryst_const)
    try:
        aaae(cell, traj.cell)
    except AssertionError:
        print "KNOWNFAIL: differrnt cell orientation"
    np.testing.assert_almost_equal(crys.volume_cell3d(cell),
                                   crys.volume_cell3d(traj.cell))
    aaae(cryst_const, crys.cell2cc3d(traj.cell))
    
    # extend arrays
    cell2d = rand(3,3)
    cc2d = crys.cell2cc(cell2d)
    traj = Trajectory(coords_frac=coords_frac,
                      cell=cell2d,
                      symbols=symbols)
    assert traj.cell.shape == (nstep,3,3)
    assert traj.cryst_const.shape == (nstep,6)
    for ii in range(traj.nstep):
        assert (traj.cell[ii,...] == cell2d).all()
        assert (traj.cryst_const[ii,:] == cc2d).all()
    
    traj = Trajectory(coords_frac=coords_frac,
                      cryst_const=cc2d,
                      symbols=symbols)
    assert traj.cell.shape == (nstep,3,3)
    assert traj.cryst_const.shape == (nstep,6)
    for ii in range(traj.nstep):
        assert (traj.cryst_const[ii,:] == cc2d).all()

    # units
    traj = Trajectory(coords_frac=coords_frac,
                    cell=cell,
                    symbols=symbols,
                    stress=stress,
                    forces=forces,
                    units={'length': 2, 'forces': 3, 'stress': 4})
    aaae(2*coords, traj.coords)                    
    aaae(3*forces, traj.forces)                    
    aaae(4*stress, traj.stress)                    
    
    # minimal input
    traj = Trajectory(coords=coords, 
                    symbols=symbols,
                    timestep=1)
    not_none_attrs = [\
        'coords',
        'ekin',
        'mass',
        'natoms',
        'nspecies',
        'nstep',
        'ntypat',
        'order',
        'symbols',
        'symbols_unique',
        'temperature',
        'timestep',
        'typat',
        'velocity',
        'znucl',
        ]
    for name in not_none_attrs:
        assert getattr(traj, name) is not None, "attr None: %s" %name
        assert eval('traj.get_%s()'%name) is not None, "getter returns None: %s" %name
    
    # iterate, check if Structures are complete
    traj = Trajectory(coords=coords, 
                      symbols=symbols,
                      cell=cell,
                      forces=forces,
                      stress=stress,
                      etot=etot,
                      timestep=1.0)
    keys = traj.attr_lst[:]
    keys.pop(keys.index('timestep'))
    struct_attrs = Structure().attr_lst
    for struct in traj:
        assert struct.is_struct, "st is not Structure"
        assert not struct.is_traj, "st is Trajectory"
    struct = traj[0]        
    for attr_name in struct_attrs:
        assert getattr(struct,attr_name) is not None    
    # slices, return traj
    tsl = traj[10:80:2]
    assert tsl.nstep == traj.nstep / 2 - 15
    assert_attrs_not_none(tsl, attr_lst=keys)
    tsl = traj[slice(10,80,2)]
    assert tsl.nstep == traj.nstep / 2 - 15
    assert_attrs_not_none(tsl, attr_lst=keys)
    tsl = traj[np.s_[10:80:2]]
    assert tsl.nstep == traj.nstep / 2 - 15
    assert_attrs_not_none(tsl, attr_lst=keys)
    assert tsl.is_traj
    
    # iteration over sliced traj
    tsl = traj[10:80:2]
    try:
        for x in tsl:
            pass
    # FIXME            
    except AttributeError:
        print("FIXME: KNOWNFAIL: AttributeError: 'Trajectory' object "
              "has no attribute 'attrs_only_traj'")
    for x in tsl.copy():
        pass

    # nstep=1 traj must at least fulfull Structure API
    aa = traj[0]
    bb = traj[0:1]
    assert_dict_with_all_types_equal(aa.__dict__, bb.__dict__, keys=aa.attr_lst)

    # repeat iter
    for i in range(2):
        cnt = 0
        for st in traj:
            cnt += 1
        assert cnt == nstep, "%i, %i" %(cnt, nstep)    
    
    # copy
    traj2 = traj.copy()
    for name in traj.attr_lst:
        val = getattr(traj,name)
        if val is not None and not (isinstance(val, types.IntType) or \
            isinstance(val, types.FloatType)):
            val2 = getattr(traj2,name)
            print "test copy:", name, type(val), type(val2)
            assert id(val2) != id(val)
            assert_all_types_equal(val2, val)
    assert_dict_with_all_types_equal(traj.__dict__, traj2.__dict__,
                                     keys=traj.attr_lst)



def test_concatenate():
    tr = get_rand_traj()
    st = get_rand_struct()
    
    # cat Structures, resulting traj needs to fulfill Structure API
    tr_cat = crys.concatenate([st]*3)
    for x in tr_cat:
        assert_dict_with_all_types_equal(x.__dict__, st.__dict__,
                                         keys=st.attr_lst) 
    assert tr_cat.nstep == 3
    assert tr_cat.timestep is None
    for attr_name in tr_cat.attrs_nstep:
        print attr_name
        if attr_name not in ['velocity', 'ekin', 'temperature']:
            assert getattr(tr_cat, attr_name).shape[0] == 3
    
    # cat Trajectory, resulting Trajectory needs to fulfill Trajectory API, but
    # timestep must be undefined
    tr_cat = crys.concatenate([tr]*3)
    assert tr_cat.timestep is None
    keys = tr.attr_lst[:]
    keys.pop(keys.index('timestep'))
    for x in [tr_cat[0:tr.nstep], 
              tr_cat[tr.nstep:2*tr.nstep], 
              tr_cat[2*tr.nstep:3*tr.nstep]]:
        assert_dict_with_all_types_equal(x.__dict__, tr.__dict__,
                                         keys=keys) 
    assert tr_cat.nstep == 300
    for attr_name in tr_cat.attrs_nstep:
        assert getattr(tr_cat, attr_name).shape[0] == 300
    

def test_mean():
    lst = [get_rand_struct() for i in range(10)]
    tr = crys.concatenate(lst)
    st_mean = crys.mean(tr)
    for attr_name in tr.attrs_nstep:
        # Structure is retutrned, so only Structure API is fulfilled
        if attr_name in st_mean.attr_lst:
            print ">>>>", attr_name
            assert np.allclose(getattr(st_mean, attr_name), 
                               getattr(tr, attr_name).mean(axis=tr.timeaxis))
        


