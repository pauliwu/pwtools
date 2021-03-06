import os
import numpy as np
import subprocess as sp
from pwtools.parse import CifFile
from pwtools import io
from .testenv import testdir
from pwtools.test import tools

def test_cif_parse():
    tools.skip_if_pkg_missing('CifFile')
    for filename in ['files/cif_struct.cif', 'files/cif_cart_struct.cif']:
        p1 = CifFile(filename).get_struct()
        assert p1.cell is not None
        assert p1.cryst_const is not None
        assert p1.symbols is not None
        assert p1.coords is not None
        assert p1.coords_frac is not None    
        
        # test writing
        filename = os.path.join(testdir, 'test_write_cif.cif')
        io.write_cif(filename, p1)
        p2 = CifFile(filename).get_struct()
        np.testing.assert_array_almost_equal(p1.coords_frac, p2.coords_frac)
        np.testing.assert_array_almost_equal(p1.coords, p2.coords)
        np.testing.assert_array_almost_equal(p1.cryst_const, p2.cryst_const)
        np.testing.assert_array_almost_equal(p1.cell, p2.cell)
        assert p1.symbols == p2.symbols


def test_cif2any():
    tools.skip_if_pkg_missing('CifFile')
    exe = os.path.join(os.path.dirname(__file__), 
                       '../../bin/cif2any.py')
    cmd = '{e} files/cif_struct.cif > cif2any.log'.format(e=exe)
    sp.run(cmd, check=True, shell=True)


def test_cif2sgroup():
    tools.skip_if_pkg_missing('CifFile')
    exe = os.path.join(os.path.dirname(__file__), 
                       '../../bin/cif2sgroup.py')
    cmd = '{e} files/cif_struct.cif > cif2sgroup.log'.format(e=exe)
    sp.run(cmd, check=True, shell=True)

