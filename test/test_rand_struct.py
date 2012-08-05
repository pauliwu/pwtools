from pwtools import crys

def test_rand_struct():
    # close_scale is small -> make sure that struct generation doesn't fail,
    # only API test here
    rs = crys.RandomStructure(symbols=['Si']*10, 
                              vol_scale=3, 
                              angle_range=[60.0, 120.0],
                              vol_range_scale=[0.7, 1.3],
                              length_range_scale=[0.7, 1.3],
                              close_scale=0.7,
                              cell_maxtry=100,
                              atom_maxtry=1000)
    st = rs.get_random_struct(fail=True)
    st = rs.get_random_struct(fail=False)
    assert st.is_struct
    assert not None in [st.coords, 
                        st.coords_frac, 
                        st.cell, 
                        st.symbols,
                        st.cryst_const]
    assert st.natoms == len(st.symbols) == 10

    # catch exception
    rs = crys.RandomStructure(symbols=['Si']*100, 
                              vol_scale=3, 
                              angle_range=[60.0, 120.0],
                              vol_range_scale=[0.7, 1.3],
                              length_range_scale=[0.7, 1.3],
                              close_scale=100,
                              cell_maxtry=1,
                              atom_maxtry=1)
    try:                              
        st = rs.get_random_struct(fail=True)
    except crys.RandomStructureFail as ex:
        print "KNOWNFAIL: catched exception: %s" %ex.msg