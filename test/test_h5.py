import os
import numpy as np
import warnings
from pwtools import io
from pwtools.test import tools
from testenv import testdir
rand = np.random.rand

def test_h5():
    try:
        import h5py
        dct1 = \
            {'/a': 'abcgs',
             '/b/c/x1': 3,
             '/b/c/x2': rand(2,3),
             }
        # writing a dct w/o leading slash will always be read back in *with*
        # leading slash             
        dct2 = \
            {'a': 'abciqo4iki',
             'b/c/x1': 3,
             'b/c/x2': rand(2,3),
             }
        for idx,dct in enumerate([dct1, dct2]):             
            h5fn = os.path.join(testdir, 'test_%i.h5' %idx)
            io.write_h5(h5fn, dct)
            read_dct = io.read_h5(h5fn)
            for kk in read_dct.keys():
                assert kk.startswith('/')
            for kk in dct.keys():
                key = '/'+kk if not kk.startswith('/') else kk
                tools.assert_all_types_equal(dct[kk], read_dct[key])
    except ImportError:
        warnings.warn("skipping test_h5, no h5py importable")
